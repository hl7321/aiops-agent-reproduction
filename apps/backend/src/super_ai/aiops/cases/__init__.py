"""诊断 case 的结构化持久化边界。"""

from super_ai.aiops.cases.models import DiagnosisCaseRecord
from super_ai.aiops.cases.service import DiagnosisCasePersistor, LegacyDiagnosisKnowledgeSaver

__all__ = ["DiagnosisCasePersistor", "DiagnosisCaseRecord", "LegacyDiagnosisKnowledgeSaver"]
