# DDARP Scripts Directory

## Current Scripts

### Active Scripts (Use These)
- **enhanced_test_system.sh** - Comprehensive testing suite
- **system_diagnostics.sh** - System debugging and diagnostics

### Backup Scripts
Old scripts have been moved to `backup_*` directories. These are kept for reference but should not be used.

## Main Automation

The primary automation is now handled by the root-level scripts:

- `./ddarp.sh` - Master control script for all operations
- `./setup.sh` - Environment setup and prerequisite installation

## Migration Guide

| Old Script | New Command |
|------------|-------------|
| `start_system.sh` | `./ddarp.sh start` |
| `stop_system.sh` | `./ddarp.sh stop` |
| `test_system.sh` | `./ddarp.sh test` |
| `setup_peers.sh` | Integrated into `./ddarp.sh start` |
| `wireguard_setup.sh` | Integrated into `./ddarp.sh setup` |
| `ddarp_automation.sh` | `./ddarp.sh` (full replacement) |
| `ddarp_one_click_start.sh` | `./setup.sh && ./ddarp.sh start` |

## Usage

For all operations, use the master control script:

```bash
# First time setup
./setup.sh
./ddarp.sh setup

# Daily operations
./ddarp.sh start
./ddarp.sh test
./ddarp.sh stop

# Debugging
./scripts/enhanced_test_system.sh
./scripts/system_diagnostics.sh
```
