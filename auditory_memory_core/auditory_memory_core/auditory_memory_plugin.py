import json
import os
import time
from collections import deque

import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from python_qt_binding.QtCore import QObject, QSize, Qt, QTimer, pyqtSignal
from python_qt_binding.QtGui import QFont
from python_qt_binding.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from rqt_gui_py.plugin import Plugin
from std_msgs.msg import String

from auditory_memory_msgs.msg import AuditoryWorkingMemoryState


class _RosQtBridge(QObject):
    graph_received = pyqtSignal(dict)
    state_received = pyqtSignal(object)
    patterns_received = pyqtSignal(dict)


class AuditoryMemoryPlugin(Plugin):
    """rqt plugin for live auditory memory graph introspection."""

    GRAPH_TOPIC_DEFAULT = '/auditory_memory/graph_viz'
    STATE_TOPIC_DEFAULT = '/auditory_memory/wm_state'
    LTM_PATTERNS_TOPIC_DEFAULT = '/auditory_memory/ltm_patterns'

    def __init__(self, context):
        super().__init__(context)
        self.setObjectName('AuditoryMemoryPlugin')

        self._node = context.node
        self._graph_sub = None
        self._state_sub = None
        self._patterns_sub = None
        self._paused = False
        self._latest_graph = None
        self._latest_state = None
        self._graph_dirty = False
        self._arousal_history = deque()
        self._layout_pos = {}
        self._last_arousal_log_s = 0.0
        self._contextual_urgency_by_episode = {}

        self._bridge = _RosQtBridge()
        self._bridge.graph_received.connect(self._on_graph_received)
        self._bridge.state_received.connect(self._on_state_received)
        self._bridge.patterns_received.connect(self._on_patterns_received)

        self._widget = QWidget()
        self._widget.setObjectName('AuditoryMemoryGraphViewer')
        self._widget.setMinimumSize(1400, 800)
        self._widget.resize(1400, 800)
        self._widget.setStyleSheet('QWidget { font-size: 10pt; }')
        if context.serial_number() > 1:
            self._widget.setWindowTitle(
                self._widget.windowTitle() + f' ({context.serial_number()})')

        self._build_ui()
        context.add_widget(self._widget)
        QTimer.singleShot(0, self._maximize_window)
        self._subscribe_graph(self.GRAPH_TOPIC_DEFAULT)
        self._subscribe_state(self.STATE_TOPIC_DEFAULT)
        self._subscribe_patterns(self.LTM_PATTERNS_TOPIC_DEFAULT)

        self._redraw_timer = QTimer(self._widget)
        self._redraw_timer.timeout.connect(self._redraw_if_needed)
        self._redraw_timer.start(500)

    def _build_ui(self):
        root = QVBoxLayout(self._widget)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel('Graph topic:'))
        self._topic_combo = QComboBox()
        self._topic_combo.setEditable(True)
        self._topic_combo.addItem(self.GRAPH_TOPIC_DEFAULT)
        self._topic_combo.lineEdit().editingFinished.connect(self._topic_changed)
        toolbar.addWidget(self._topic_combo, stretch=1)
        self._pause_button = QPushButton('Pause')
        self._pause_button.clicked.connect(self._toggle_pause)
        toolbar.addWidget(self._pause_button)
        clear_button = QPushButton('Clear')
        clear_button.clicked.connect(self._clear)
        toolbar.addWidget(clear_button)
        snapshot_button = QPushButton('Snapshot')
        snapshot_button.clicked.connect(self._snapshot)
        toolbar.addWidget(snapshot_button)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, stretch=1)

        self._graph_figure = Figure(figsize=(11, 8))
        self._graph_canvas = FigureCanvas(self._graph_figure)
        self._graph_canvas.setMinimumSize(900, 700)
        self._graph_ax = self._graph_figure.add_subplot(111)
        splitter.addWidget(self._graph_canvas)

        side = QWidget()
        side.setMinimumWidth(280)
        side_layout = QVBoxLayout(side)
        side_layout.addWidget(QLabel('Arousal'))
        self._arousal_value = QLabel('Arousal: 0.00')
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self._arousal_value.setFont(font)
        side_layout.addWidget(self._arousal_value)
        self._arousal_bar = QProgressBar()
        self._arousal_bar.setRange(0, 100)
        self._arousal_bar.setMinimumHeight(30)
        self._arousal_bar.setTextVisible(True)
        side_layout.addWidget(self._arousal_bar)
        self._focused_sound = QLabel('Focused sound: -')
        self._focused_location = QLabel('Focused location: -')
        side_layout.addWidget(self._focused_sound)
        side_layout.addWidget(self._focused_location)
        side_layout.addWidget(QLabel('Active episodes'))
        self._episode_list = QListWidget()
        self._episode_list.setUniformItemSizes(False)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._episode_list)
        side_layout.addWidget(scroll, stretch=1)
        side_layout.addWidget(QLabel('Long-Term Memory Patterns'))
        self._patterns_list = QListWidget()
        self._patterns_list.setUniformItemSizes(False)
        self._patterns_list.addItem('Waiting for Long-Term Memory patterns...')
        side_layout.addWidget(self._patterns_list, stretch=1)
        side_layout.addWidget(QLabel('Arousal history'))
        self._history_figure = Figure(figsize=(3.6, 2.1))
        self._history_canvas = FigureCanvas(self._history_figure)
        self._history_canvas.setMinimumHeight(150)
        self._history_ax = self._history_figure.add_subplot(111)
        side_layout.addWidget(self._history_canvas)
        splitter.addWidget(side)
        splitter.setSizes([1100, 300])

        self._draw_empty_graph()
        self._draw_history()

    def _subscribe_graph(self, topic):
        if self._graph_sub is not None:
            self._node.destroy_subscription(self._graph_sub)
        self._graph_sub = self._node.create_subscription(String, topic, self._graph_cb, 10)

    def _subscribe_state(self, topic):
        if self._state_sub is not None:
            self._node.destroy_subscription(self._state_sub)
        self._state_sub = self._node.create_subscription(
            AuditoryWorkingMemoryState, topic, self._state_cb, 10)

    def _subscribe_patterns(self, topic):
        if self._patterns_sub is not None:
            self._node.destroy_subscription(self._patterns_sub)
        self._patterns_sub = self._node.create_subscription(String, topic, self._patterns_cb, 10)

    def _graph_cb(self, msg):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self._node.get_logger().warning('Invalid auditory graph_viz JSON received')
            return
        self._bridge.graph_received.emit(payload)

    def _state_cb(self, msg):
        self._bridge.state_received.emit(msg)

    def _patterns_cb(self, msg):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self._node.get_logger().warning('Invalid auditory ltm_patterns JSON received')
            return
        self._bridge.patterns_received.emit(payload)

    def _on_graph_received(self, payload):
        if self._paused:
            return
        self._latest_graph = payload
        self._graph_dirty = True
        self._contextual_urgency_by_episode = {
            node.get('id', ''): float(node.get('contextual_urgency', 0.0))
            for node in payload.get('nodes', [])
            if node.get('type') == 'episode'
        }
        arousal = float(payload.get('arousal', 0.0))
        self._log_arousal_source('graph_viz', arousal)
        self._append_arousal(arousal)
        self._set_arousal(arousal)
        self._focused_sound.setText(
            f"Focused sound: {payload.get('focused_sound', '-') or '-'}")
        self._focused_location.setText(
            f"Focused location: {payload.get('focused_location', '-') or '-'}")
        self._refresh_episode_list()

    def _on_state_received(self, msg):
        if self._paused:
            return
        self._latest_state = msg
        arousal = float(msg.arousal_level)
        self._log_arousal_source('wm_state', arousal)
        self._set_arousal(arousal)
        self._append_arousal(arousal)
        self._focused_sound.setText(f'Focused sound: {msg.focused_sound or "-"}')
        self._focused_location.setText(f'Focused location: {msg.focused_location or "-"}')
        self._refresh_episode_list()

    def _refresh_episode_list(self):
        if self._latest_state is None:
            return
        self._episode_list.clear()
        for episode in self._latest_state.active_episodes:
            co = ', '.join(episode.co_occurring_sounds) or '-'
            contextual_urgency = self._contextual_urgency_by_episode.get(episode.episode_id, 0.0)
            self._episode_list.addItem(
                f'{episode.sound_type} @ {episode.location_id} | '
                f'novelty={episode.novelty:.2f} | urgency={contextual_urgency:.2f} | '
                f'arousal={episode.arousal_contribution:.2f} | co={co} | '
                f'ready={episode.consolidation_ready}')
            self._episode_list.item(self._episode_list.count() - 1).setSizeHint(QSize(260, 40))
        self._draw_history()

    def _on_patterns_received(self, payload):
        if self._paused:
            return
        self._patterns_list.clear()
        entries = self._format_patterns(payload)
        if not entries:
            entries = ['Waiting for Long-Term Memory patterns...']
        for entry in entries:
            self._patterns_list.addItem(entry)
            self._patterns_list.item(self._patterns_list.count() - 1).setSizeHint(QSize(260, 24))

    def _format_patterns(self, payload):
        entries = []
        sound_locations = payload.get('sound_location_patterns', [])[:5]
        if sound_locations:
            entries.append('Sound-location')
            for item in sound_locations:
                entries.append(
                    self._pattern_line(
                        item.get('sound', '?'),
                        item.get('location', '?'),
                        '->',
                        f"w={float(item.get('weight', 0.0)):.2f}"))
        time_patterns = payload.get('time_patterns', [])[:5]
        if time_patterns:
            self._append_section_gap(entries)
            entries.append('Time-of-day')
            for item in time_patterns:
                entries.append(
                    self._pattern_line(
                        item.get('sound', '?'),
                        item.get('period', '?'),
                        '->',
                        f"count={int(item.get('count', 0))}"))
        co_occurrences = payload.get('co_occurrence_patterns', [])[:5]
        if co_occurrences:
            self._append_section_gap(entries)
            entries.append('Co-occurrence')
            for item in co_occurrences:
                entries.append(
                    self._pattern_line(
                        item.get('sound_a', '?'),
                        item.get('sound_b', '?'),
                        '<->',
                        f"w={float(item.get('weight', 0.0)):.2f}"))
        recent_updates = payload.get('recent_updates', [])[:5]
        if recent_updates:
            self._append_section_gap(entries)
            entries.append('Recent updates')
            for item in recent_updates:
                entries.append(f"- {self._short_update(item)}")
        return entries

    def _append_section_gap(self, entries):
        if entries and entries[-1] != '':
            entries.append('')

    def _pattern_line(self, left, right, relation, value):
        pattern = f'{left} {relation} {right}'
        return f'- {pattern:<34} {value}'

    def _short_update(self, item):
        description = item.get('description', 'Pattern updated')
        description = description.replace('Pattern reinforced: ', 'reinforced ')
        return description.replace(' <-> ', ' <-> ').replace(' -> ', ' -> ')

    def _redraw_if_needed(self):
        if self._graph_dirty and self._latest_graph is not None:
            self._graph_dirty = False
            self._draw_graph(self._latest_graph)

    def _draw_graph(self, payload):
        graph = nx.DiGraph()
        for node in payload.get('nodes', []):
            graph.add_node(node.get('id', ''), **node)
        for edge in payload.get('edges', []):
            graph.add_edge(edge.get('source', ''), edge.get('target', ''), **edge)

        self._graph_ax.clear()
        self._graph_ax.set_title('Auditory Working Memory Graph')
        self._graph_ax.axis('off')
        if not graph.nodes:
            self._draw_empty_graph()
            return

        self._layout_pos = nx.spring_layout(graph, seed=7, pos=self._layout_pos or None)
        edge_colors = {
            'co_occurs': '#f28e2b',
            'heard_in': '#7b4ab2',
            'heard_at': '#7b4ab2',
            'typical_for': '#59a14f',
            'typical_sound': '#59a14f',
            'precedes': '#e15759',
        }
        for source, target, attrs in graph.edges(data=True):
            relation = attrs.get('relation_type', '')
            weight = max(0.05, float(attrs.get('weight', 0.0)))
            nx.draw_networkx_edges(
                graph,
                self._layout_pos,
                edgelist=[(source, target)],
                ax=self._graph_ax,
                arrows=True,
                arrowstyle='-|>',
                arrowsize=16,
                width=2.0 + 4.0 * min(1.0, weight),
                edge_color=edge_colors.get(relation, '#777777'),
                alpha=0.35 + min(0.6, weight),
                connectionstyle='arc3,rad=0.08',
            )

        type_styles = {
            'sound_type': ('#4e79a7', 'o', 1000),
            'location': ('#59a14f', 's', 1150),
            'episode': ('#9d9d9d', 'o', 800),
        }
        for node_type, (color, marker, base_size) in type_styles.items():
            nodes = [n for n, a in graph.nodes(data=True) if a.get('type') == node_type]
            if not nodes:
                continue
            sizes = []
            alphas = []
            edgecolors = []
            linewidths = []
            for node_id in nodes:
                attrs = graph.nodes[node_id]
                activation = max(0.0, min(1.0, float(attrs.get('activation', 0.0))))
                sizes.append(base_size * (0.75 + activation))
                alphas.append(0.20 + 0.80 * activation)
                focused = bool(attrs.get('is_focused', False))
                edgecolors.append('#d62728' if focused else '#222222')
                linewidths.append(2.5 if focused else 0.8)
            xs = [self._layout_pos[n][0] for n in nodes]
            ys = [self._layout_pos[n][1] for n in nodes]
            for x, y, size, alpha, edgecolor, linewidth in zip(
                    xs, ys, sizes, alphas, edgecolors, linewidths):
                self._graph_ax.scatter(
                    [x], [y], s=size, c=color, marker=marker, alpha=alpha,
                    edgecolors=edgecolor, linewidths=linewidth, zorder=3)

        for node_id, (x, y) in self._layout_pos.items():
            focused = bool(graph.nodes[node_id].get('is_focused', False))
            self._graph_ax.text(
                x,
                y,
                node_id.split(':', 1)[-1],
                fontsize=11,
                fontweight='bold' if focused else 'normal',
                color='#111111',
                ha='center',
                va='center',
                zorder=4,
            )
        self._graph_figure.tight_layout()
        self._graph_canvas.draw_idle()

    def _maximize_window(self):
        window = self._widget.window()
        if window is not None:
            window.resize(1400, 800)
            window.showMaximized()

    def _draw_empty_graph(self):
        self._graph_ax.clear()
        self._graph_ax.axis('off')
        self._graph_ax.text(0.5, 0.5, 'Waiting for auditory memory graph...',
                            ha='center', va='center')
        self._graph_canvas.draw_idle()

    def _append_arousal(self, value):
        now = time.monotonic()
        self._arousal_history.append((now, max(0.0, min(1.0, value))))
        while self._arousal_history and now - self._arousal_history[0][0] > 60.0:
            self._arousal_history.popleft()

    def _set_arousal(self, value):
        value = max(0.0, min(1.0, value))
        self._arousal_value.setText(f'Arousal: {value:.2f}')
        self._arousal_bar.setValue(int(value * 100))
        self._arousal_bar.setFormat(f'{value:.2f} / 1.00')
        color = '#2ca02c'
        if value >= 0.6:
            color = '#d62728'
        elif value >= 0.3:
            color = '#f1c40f'
        self._arousal_bar.setStyleSheet(
            'QProgressBar::chunk { background-color: %s; }' % color)

    def _log_arousal_source(self, source, value):
        now = time.monotonic()
        if value <= 0.01 or now - self._last_arousal_log_s < 2.0:
            return
        self._last_arousal_log_s = now
        self._node.get_logger().info(f'Arousal received from {source}: {value:.3f}')

    def _draw_history(self):
        self._history_ax.clear()
        self._history_ax.set_ylim(0.0, 1.0)
        self._history_ax.set_xlim(-60.0, 0.0)
        self._history_ax.set_ylabel('arousal')
        self._history_ax.set_xlabel('s')
        if self._arousal_history:
            now = time.monotonic()
            xs = [t - now for t, _ in self._arousal_history]
            ys = [v for _, v in self._arousal_history]
            self._history_ax.plot(xs, ys, color='#d62728', linewidth=1.8)
        self._history_figure.tight_layout()
        self._history_canvas.draw_idle()

    def _topic_changed(self):
        topic = self._topic_combo.currentText().strip()
        if topic:
            self._subscribe_graph(topic)

    def _toggle_pause(self):
        self._paused = not self._paused
        self._pause_button.setText('Resume' if self._paused else 'Pause')

    def _clear(self):
        self._latest_graph = None
        self._latest_state = None
        self._graph_dirty = False
        self._layout_pos = {}
        self._arousal_history.clear()
        self._contextual_urgency_by_episode = {}
        self._episode_list.clear()
        self._patterns_list.clear()
        self._patterns_list.addItem('Waiting for Long-Term Memory patterns...')
        self._arousal_value.setText('Arousal: 0.00')
        self._focused_sound.setText('Focused sound: -')
        self._focused_location.setText('Focused location: -')
        self._set_arousal(0.0)
        self._draw_empty_graph()
        self._draw_history()

    def _snapshot(self):
        directory = os.path.expanduser('~/auditory_memory_snapshots')
        os.makedirs(directory, exist_ok=True)
        filename = time.strftime('auditory_memory_graph_%Y%m%d_%H%M%S.png')
        path = os.path.join(directory, filename)
        self._graph_figure.savefig(path, dpi=160)
        self._node.get_logger().info(f'Saved auditory memory snapshot: {path}')

    def shutdown_plugin(self):
        if self._graph_sub is not None:
            self._node.destroy_subscription(self._graph_sub)
            self._graph_sub = None
        if self._state_sub is not None:
            self._node.destroy_subscription(self._state_sub)
            self._state_sub = None
        if self._patterns_sub is not None:
            self._node.destroy_subscription(self._patterns_sub)
            self._patterns_sub = None
