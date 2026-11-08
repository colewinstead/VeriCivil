"""Browser adapter for the separately maintained, unchanged Guardrail engine."""

from pathlib import Path
import sys

# Upstream uses absolute guardrail_* imports in both desktop and portable engine modules.
_upstream = str(Path(__file__).with_name("upstream"))
if _upstream not in sys.path:
    sys.path.append(_upstream)
