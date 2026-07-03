from setuptools import find_packages, setup

package_name = 'auditory_memory_core'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    # rqt discovers Python plugins through plugin.xml installed in share/<package>.
    # This is an ament_python package, so no CMakeLists.txt plugin install entry is needed.
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name, ['plugin.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='gentlebots',
    maintainer_email='igonzf06@estudiantes.unileon.es',
    description='Core nodes, simulators, and rqt plugin for auditory memory.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'working_memory_node = auditory_memory_core.auditory_memory_node:main',
            'auditory_memory_node = auditory_memory_core.auditory_memory_node:main',
            'long_term_memory_node = auditory_memory_core.long_term_memory_node:main',
            'auditory_day_simulator = auditory_memory_core.auditory_day_simulator:main',
        ],
    },
)
