import argparse
import os
import tempfile
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

import yaml
from ament_index_python.packages import PackageNotFoundError, get_package_share_directory

from auditory_memory_core.memory import LongTermMemory, WorkingMemory
from fmea_risk_module.logic_fmearisk import RiskPipeline, interpret_bt_response, interpret_rpn


NOVELTY_THRESHOLD = 0.70
CONGRUENCE_THRESHOLD = 0.50
ACTION_BT_RESPONSES = {'SLOW_DOWN', 'STOP_AND_ASSESS', 'EMERGENCY_STOP'}


@dataclass(frozen=True)
class DemoEvent:
    hour: int
    minute: int
    sound: str
    location: str
    note: str
    current_task: str
    task_importance: str
    habituation_repetitions_after: int = 0


def _seed_routine_memory(ltm: LongTermMemory, midnight_s: float) -> None:
    routine_events = [
        ('alarm', 'bedroom', 7, 0),
        ('water_running', 'bathroom', 7, 35),
        ('coffee_machine', 'kitchen', 8, 5),
        ('tv_on', 'living_room', 20, 35),
        ('voices', 'living_room', 20, 36),
        ('soft_voices', 'bedroom', 22, 15),
    ]
    for _ in range(7):
        for sound, location, hour, minute in routine_events:
            ts = midnight_s + hour * 3600 + minute * 60
            ltm.consolidate_episode(sound, location, ts, ts + 2.0, [], novelty=0.2)


def _demo_events() -> List[DemoEvent]:
    return [
        DemoEvent(
            10,
            15,
            'strange_rattle',
            'hallway',
            'Primera vez que se oye un sonido raro: se inspecciona si la tarea lo permite.',
            'ordenar objetos en la sala',
            'low',
            habituation_repetitions_after=8,
        ),
        DemoEvent(
            14,
            30,
            'strange_rattle',
            'hallway',
            'El mismo sonido tras varias repeticiones consolidadas: ya es habitual.',
            'ordenar objetos en la sala',
            'low',
        ),
        DemoEvent(
            15,
            0,
            'doorbell_chime',
            'hallway',
            'Timbre: no es peligroso, pero la tarea actual es interrumpible.',
            'ordenar objetos en la sala',
            'low',
        ),
        DemoEvent(
            21,
            40,
            'alarm',
            'living_room',
            'Sonido familiar en lugar/hora incongruentes con persona cerca.',
            'patrulla rutinaria',
            'medium',
        ),
    ]


def _default_config_path() -> str:
    try:
        share_dir = get_package_share_directory('auditory_memory_core')
        return os.path.join(share_dir, 'config', 'auditory_risk_demo_fmea.yaml')
    except PackageNotFoundError:
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config',
            'auditory_risk_demo_fmea.yaml',
        )


def _load_config(path: str) -> Dict:
    with open(path, 'r', encoding='utf-8') as stream:
        return yaml.safe_load(stream) or {}


def _period_label(hour: int) -> str:
    if 5 <= hour < 12:
        return 'morning'
    if 12 <= hour < 17:
        return 'afternoon'
    if 17 <= hour < 22:
        return 'evening'
    return 'night'


def _clamp_score(value: float) -> int:
    return max(1, min(10, round(value)))


def _memory_flags(memory: WorkingMemory, episode_id: str) -> Dict:
    attrs = memory.episode_attrs(episode_id)
    focused_sound, focused_location = memory.focused_sound_location()
    return {
        'new_sound': float(attrs.get('familiarity', 0.0)) < 0.30,
        'incongruent_location': (
            bool(attrs.get('location_available', False))
            and float(attrs.get('location_congruence', 0.0)) < CONGRUENCE_THRESHOLD
        ),
        'attention_relevant': (
            attrs.get('sound_type') == focused_sound
            and attrs.get('location_id') == focused_location
        ),
        'context_label': attrs.get('context_label', ''),
        'familiarity': float(attrs.get('familiarity', 0.0)),
        'novelty': float(attrs.get('novelty', 0.0)),
        'location_congruence': float(attrs.get('location_congruence', 0.0)),
        'arousal_contribution': float(attrs.get('arousal_contribution', 0.0)),
    }


def _build_risk_context(event: DemoEvent, flags: Dict, config: Dict, timestamp_s: float) -> Tuple[Dict, Dict]:
    adapter = config.get('memory_to_fmea', {})
    defaults = adapter.get('defaults', {})
    overrides = adapter.get('sound_overrides', {}).get(event.sound, {})
    base = dict(adapter.get('base_attributes', {}))

    novelty_to_hazard = float(overrides.get('novelty_to_hazard', adapter.get('novelty_to_hazard', 0.0)))
    incongruence_to_obstruction = float(
        overrides.get('incongruence_to_obstruction', adapter.get('incongruence_to_obstruction', 0.0)))
    attention_to_interaction = float(
        overrides.get('attention_to_interaction', adapter.get('attention_to_interaction', 0.0)))
    familiarity_relief = float(overrides.get('familiarity_relief', adapter.get('familiarity_relief', 0.0)))
    incongruence = 1.0 - flags['location_congruence']
    attention = 1.0 if flags['attention_relevant'] else 0.0

    hazard = (
        float(overrides.get('hazard_score', base.get('hazard_score', 1.0)))
        + flags['novelty'] * novelty_to_hazard
        + float(overrides.get('hazard_bonus', 0.0))
        - flags['familiarity'] * familiarity_relief
    )
    obstruction = (
        float(overrides.get('obstruction_score', base.get('obstruction_score', 1.0)))
        + incongruence * incongruence_to_obstruction
        + float(overrides.get('obstruction_bonus', 0.0))
    )
    interaction = (
        float(overrides.get('interaction_level', base.get('interaction_level', 1.0)))
        + attention * attention_to_interaction
        + float(overrides.get('interaction_bonus', 0.0))
    )
    attributes = {
        'hazard_score': _clamp_score(hazard),
        'movability_score': _clamp_score(float(overrides.get('movability_score', base.get('movability_score', 8.0)))),
        'attentiveness_score': _clamp_score(float(overrides.get('attentiveness_score', base.get('attentiveness_score', 8.0)))),
        'interaction_level': _clamp_score(interaction),
        'obstruction_score': _clamp_score(obstruction),
        'is_inanimate': bool(overrides.get('is_inanimate', base.get('is_inanimate', True))),
    }
    trace = {
        'hazard_raw': hazard,
        'obstruction_raw': obstruction,
        'interaction_raw': interaction,
        'familiarity_relief': flags['familiarity'] * familiarity_relief,
    }
    context = {
        'caption': f'SIMULATED from memory evidence: {event.sound} in {event.location}',
        'frame_id': int(timestamp_s),
        'timestamp': timestamp_s,
        'environment': {
            'time_of_day': 'night' if _period_label(event.hour) == 'night' else 'day',
            'presence_of_others': bool(overrides.get('presence_of_others', defaults.get('presence_of_others', False))),
            'light_conditions': overrides.get('light_conditions', defaults.get('light_conditions', 'bright')),
            'environment_type': overrides.get('environment_type', defaults.get('environment_type', 'office')),
        },
        'entities': [
            {
                'type': overrides.get('entity_type', defaults.get('entity_type', 'auditory_event')),
                'source': 'simulated_from_memory_for_demo',
                'spatial': [0.0, 0.0, float(overrides.get('depth_m', defaults.get('depth_m', 3.0)))],
                'attributes': attributes,
            }
        ],
    }
    return context, trace


def _risk_assessment(context: Dict) -> Tuple[Dict, str, bool]:
    risk_result = RiskPipeline().evaluate_from_full(context)
    per_entity = risk_result.get('per_entity', [])
    worst = max(per_entity, key=lambda item: float(item.get('RPN_final', 0.0)), default=None)
    worst_rpn = float(worst.get('RPN_final', 0.0)) if worst else 0.0
    bt_response = interpret_bt_response(worst_rpn)
    return {
        'risk_level': interpret_rpn(worst_rpn),
        'bt_response': bt_response,
        'worst_rpn': worst_rpn,
        'worst_entity': worst,
        'raw_result': risk_result,
    }, bt_response, bt_response in ACTION_BT_RESPONSES


def _task_rank(label: str, policy: Dict) -> int:
    order = policy.get('task_importance_order', {})
    return int(order.get(label, order.get('medium', 2)))


def _below_task_threshold(event: DemoEvent, policy: Dict, threshold_key: str) -> bool:
    threshold = policy.get(threshold_key, 'high')
    return _task_rank(event.task_importance, policy) < _task_rank(threshold, policy)


def _final_decision(
    event: DemoEvent,
    flags: Dict,
    should_check_risk: bool,
    requires_risk_action: bool,
    config: Dict,
) -> Tuple[str, str]:
    policy = config.get('attention_policy', {})
    attention_request_sounds = set(policy.get('attention_request_sounds', []))
    if should_check_risk and requires_risk_action:
        return 'ACTUAR', 'el modulo de riesgo requiere accion'
    if event.sound in attention_request_sounds:
        if _below_task_threshold(event, policy, 'interrupt_attention_requests_below'):
            return 'ACTUAR_ATENDER_TIMBRE', 'peticion de atencion y tarea interrumpible'
        return 'CONTINUAR', 'peticion de atencion pospuesta por tarea importante'
    if bool(policy.get('attend_unfamiliar_sounds', False)) and flags['new_sound']:
        if _below_task_threshold(event, policy, 'inspect_unfamiliar_below'):
            return 'ACTUAR_INSPECCIONAR_SONIDO', 'sonido no familiar y tarea interrumpible'
    return 'CONTINUAR', 'riesgo bajo, sonido habitual o tarea actual prioritaria'


def _format_flags(flags: Dict) -> str:
    active = [
        label for key, label in (
            ('new_sound', 'nuevo'),
            ('incongruent_location', 'incongruente_con_lugar'),
            ('attention_relevant', 'relevante_para_atencion'),
        ) if flags[key]
    ]
    return ', '.join(active) if active else 'sin disparador'


def _apply_habituation(ltm: LongTermMemory, event: DemoEvent, timestamp_s: float) -> None:
    for repetition in range(event.habituation_repetitions_after):
        repeated_ts = timestamp_s + (repetition + 1) * 600.0
        ltm.consolidate_episode(
            event.sound,
            event.location,
            repeated_ts,
            repeated_ts + 2.0,
            [],
            novelty=0.1,
        )


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description='Demo connecting auditory memory with FMEA risk.')
    parser.add_argument('--fmea-config', default=_default_config_path())
    args = parser.parse_args(argv)

    config = _load_config(args.fmea_config)
    midnight_s = time.mktime(time.localtime()[:3] + (0, 0, 0) + time.localtime()[6:])
    with tempfile.TemporaryDirectory(prefix='auditory_risk_demo_') as tmp_dir:
        ltm = LongTermMemory(
            os.path.join(tmp_dir, 'ltm.json'),
            location_missing_neutral_congruence=0.0,
        )
        _seed_routine_memory(ltm, midnight_s)
        memory = WorkingMemory(ltm)

        print('Demo memoria auditiva + riesgo FMEA')
        print('Componentes reales: LongTermMemory, WorkingMemory, RiskPipeline, interpret_rpn, interpret_bt_response')
        print(f'YAML FMEA demo: {args.fmea_config}')
        print('Datos simulados: entities/environment/caption para RiskPipeline, generados desde evidencia real de memoria segun el YAML.')
        print('Dato simulado adicional: tarea actual e importancia, usado solo para arbitrar interrupciones como el timbre.')
        print('Configuracion demo: asociaciones lugar-sonido ausentes cuentan como incongruencia para hacer visible el enlace con riesgo.')
        print('')

        for index, event in enumerate(_demo_events(), start=1):
            timestamp_s = midnight_s + event.hour * 3600 + event.minute * 60
            episode_id = memory.observe(event.sound, event.location, timestamp_s)
            flags = _memory_flags(memory, episode_id)
            should_check_risk = any((
                flags['new_sound'],
                flags['incongruent_location'],
                flags['attention_relevant'],
                flags['novelty'] >= NOVELTY_THRESHOLD,
            ))
            risk_context, adapter_trace = _build_risk_context(event, flags, config, timestamp_s)
            risk, bt_response, requires_action = _risk_assessment(risk_context)
            final_decision, decision_reason = _final_decision(
                event, flags, should_check_risk, requires_action, config)
            worst_entity = risk['worst_entity'] or {}
            attrs = worst_entity.get('attributes', {})

            print(f'Evento {index}: {event.sound} @ {event.location} ({event.hour:02d}:{event.minute:02d}, {_period_label(event.hour)})')
            print(f'  Contexto: {event.note}')
            print(f'  Tarea actual simulada: {event.current_task} | importancia={event.task_importance}')
            print(
                '  Memoria: '
                f"flags={_format_flags(flags)} | "
                f"context_label={flags['context_label']} | "
                f"familiarity={flags['familiarity']:.2f} | "
                f"novelty={flags['novelty']:.2f} | "
                f"location_congruence={flags['location_congruence']:.2f} | "
                f"arousal_contribution={flags['arousal_contribution']:.2f}"
            )
            print(
                '  FMEA demo YAML -> atributos: '
                f"hazard={attrs.get('hazard_score')} | "
                f"obstruction={attrs.get('obstruction_score')} | "
                f"interaction={attrs.get('interaction_level')} | "
                f"familiarity_relief={adapter_trace['familiarity_relief']:.2f}"
            )
            print(
                '  Riesgo: '
                f"source=simulated_from_memory_for_demo | "
                f"worst_entity={worst_entity.get('type', 'none')} | "
                f"RPN={risk['worst_rpn']:.2f} ({risk['risk_level']}) | "
                f"bt_response={bt_response}"
            )
            print(f'  Decision final: {final_decision} | motivo={decision_reason}')
            if event.habituation_repetitions_after:
                _apply_habituation(ltm, event, timestamp_s)
                memory = WorkingMemory(ltm)
                print(f'  Aprendizaje simulado: {event.habituation_repetitions_after} repeticiones consolidadas para habituacion.')
            print('')


if __name__ == '__main__':
    main()
