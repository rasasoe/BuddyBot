"""
BuddyBot System Package

This package provides system-level command arbitration and safety supervision
for BuddyBot, ensuring safe and coordinated operation of all subsystems.

Key Components:
- Command Multiplexer: Safely selects and prioritizes velocity commands
- Mode Manager: Tracks and coordinates system operating modes
- Safety Supervisor: Monitors emergency conditions and enforces safety protocols

Safety Philosophy:
- Single point of command authority prevents conflicting instructions
- Hierarchical priority system ensures safety overrides take precedence
- Transparent decision making for debugging and verification
"""

__version__ = "0.0.0"