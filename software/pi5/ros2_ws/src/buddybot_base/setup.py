from setuptools import setup
import os
from glob import glob

package_name = 'buddybot_base'

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
    description='Base functionality for BuddyBot: Pico communication bridge',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'pico_bridge_node = buddybot_base.pico_bridge_node:main',
            'encoder_odom_node = buddybot_base.encoder_odom_node:main',
        ],
    },
)
