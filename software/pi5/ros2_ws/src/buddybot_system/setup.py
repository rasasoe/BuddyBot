from setuptools import setup
import os
from glob import glob

package_name = 'buddybot_system'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='todo@todo.com',
    description='System-level command arbitration and safety supervision for BuddyBot',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'command_mux_node = buddybot_system.command_mux_node:main',
            'mode_manager_node = buddybot_system.mode_manager_node:main',
            'safety_supervisor_node = buddybot_system.safety_supervisor_node:main',
        ],
    },
)