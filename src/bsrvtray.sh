#!/bin/bash
source {{INSTALL_DIR}}/venv/bin/activate
cd {{INSTALL_DIR}}
python3 -m bsrvtray "$@"