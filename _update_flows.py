#!/usr/bin/env python3
"""Update flows.py with new domain-named subflows."""
import sys

path = 'data/pipelines/flows.py'
with open(path) as f:
    content = f.read()

old_import = (
    'from data.pipelines.subflows import (\n'
    '    subflow_extraction,\n'
    '    subflow_transformation,\n'
    '    subflow_loading,\n'
    '    subflow_snapshot_export,\n'
    ')'
)
new_import = (
    'from data.pipelines.subflows import (\n'
    '    subflow_supply_event_ingestion,\n'
    '    subflow_supply_kpi_calculation,\n'
    '    subflow_clinic_performance_publishing,\n'
    '    subflow_clinic_kpi_snapshot,\n'
    ')'
)
if old_import not in content:
    print("ERROR: old import not found!", file=sys.stderr)
    sys.exit(1)
content = content.replace(old_import, new_import)

# Replace function calls
content = content.replace('extraction_result = subflow_extraction(', 'extraction_result = subflow_supply_event_ingestion(')
content = content.replace('transform_result = subflow_transformation(', 'transform_result = subflow_supply_kpi_calculation(')
content = content.replace('snapshot_state = subflow_snapshot_export.submit(', 'snapshot_state = subflow_clinic_kpi_snapshot.submit(')
content = content.replace('loading_result = subflow_loading(', 'loading_result = subflow_clinic_performance_publishing(')

# Docstring references
content = content.replace('1. :func:`subflow_extraction`', '1. :func:`subflow_supply_event_ingestion`')
content = content.replace('2. :func:`subflow_transformation`', '2. :func:`subflow_supply_kpi_calculation`')
content = content.replace('3. :func:`subflow_snapshot_export`', '3. :func:`subflow_clinic_kpi_snapshot`')
content = content.replace('4. :func:`subflow_loading`', '4. :func:`subflow_clinic_performance_publishing`')

with open(path, 'w') as f:
    f.write(content)
print("flows.py updated OK")