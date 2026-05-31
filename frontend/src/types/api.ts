export type Lens = 'general' | 'fsi' | 'healthcare'

export interface NonFunctionals {
  sla_percent?: number
  regions?: number
  rto_minutes?: number
  rpo_minutes?: number
  compliance_flags?: string[]
}

export interface ArchitectureRequest {
  workload_description: string
  non_functionals: NonFunctionals
  lens: Lens
}

export interface ServiceRecommendation {
  category: string
  service: string
  reasoning: string
}

export type RiskLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'GOOD_PRACTICE'

export interface ChecklistItem {
  question: string
  risk_level: RiskLevel
  finding: string
  improvement_suggestion: string
}

export interface WellArchitectedChecklist {
  operational_excellence: ChecklistItem[]
  security: ChecklistItem[]
  reliability: ChecklistItem[]
  performance_efficiency: ChecklistItem[]
  cost_optimization: ChecklistItem[]
  sustainability: ChecklistItem[]
}

export interface CostTier {
  tier: 'dev' | 'staging' | 'prod'
  monthly_estimate_hint: string
  assumptions: string
}

export interface ArchitectureResponse {
  architecture_summary: string
  service_recommendations: ServiceRecommendation[]
  mermaid_diagram: string
  well_architected_checklist: WellArchitectedChecklist
  cost_tiers: CostTier[]
}
