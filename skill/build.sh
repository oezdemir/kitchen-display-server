#!/bin/sh
# Build this skill into dist/<name>-<version>-<target>.hskill
#
#   ./build.sh                 # target linux-x86_64 (bot0)
#
# Self-contained: needs only python3 (always present), plus pip for python-runtime
# skills. No external tooling and no PATH setup — clone the skill and run this.
exec python3 "$(dirname "$0")/build.py" "$@"
