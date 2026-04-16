import { API_URL } from '../../config';

// Types
export interface User {
  userId: string;
  name: string;
  email: string;
  threads: Record<string, Thread>;
}

export interface ThreadInstruction {
  id: string;
  text: string;
  selected: boolean;
}

export interface Thread {
  thread_name: string;
  createdAt: string;
  updatedAt: string;
  documents: Document[];
  chats: Chat[];
  instructions?: ThreadInstruction[];
}

export interface Document {
  docId: string;
  title: string;
  type: string;
  time_uploaded: string;
  file_name: string;
}

export interface SQLSourceDocument {
  doc_id: string;
  title: string;
  file_name?: string;
  tables: string[];
}

export interface SQLExecutionSource {
  query: string;
  status: 'success' | 'failed';
  tables: string[];
  documents: SQLSourceDocument[];
}

export interface Chat {
  type: 'user' | 'agent';
  content: string;
  timestamp: string;
  // Enhanced metadata fields from backend
  thought_process?: string; // For Deep Reasoning output
  sources?: {
    documents_used: Array<{
      title: string;
      document_id: string;
      page_no: number;
    }>;
    web_used: Array<{
      title: string;
      url: string;
      favicon: string | null;
    }>;
    charts_used?: Array<{
      chart_id: string;
      title: string;
      description?: string;
      chart_type: string;
      x_key?: string;
      y_keys?: string[];
      row_count?: number;
      item_url: string;
      download_json_url?: string;
      download_csv_url?: string;
    }>;
    sql_used?: SQLExecutionSource[];
  };
}

export interface DeleteChatResponse {
  status: string;
  message: string;
  thread_id: string;
  deleted_index: number;
  chats: Chat[];
}

export interface ClearChatsResponse {
  status: string;
  message: string;
  thread_id: string;
  chats: Chat[];
}

export interface DeleteDocumentResponse {
  status: string;
  message: string;
  thread_id: string;
  deleted_doc_id: string;
  documents: Document[];
}

export interface AddExistingDocumentResponse {
  status: string;
  message: string;
  thread_id: string;
  document: Document;
}

export interface LoginResponse {
  status: string;
  message: string;
  user: User;
  token: string;
}

export interface UploadResponse {
  status: string;
  message: string;
  thread_id: string;
  documents: Document[];
}

export interface QueryResponse {
  thread_id: string;
  user_id: string;
  question: string;
  answer: string;
  use_self_knowledge?: boolean;
  // Enhanced metadata fields
  thought_process?: string;
  // Original shape (legacy)
  docs_used?: Array<{
    title: string;
    document_id: string;
    page_no: number;
  }>;
  web_used?: Array<{
    title: string;
    url: string;
    favicon: string | null;
  }>;
  // Newer shape returned by backend under a `sources` object
  sources?: {
    documents_used?: Array<{
      title: string;
      document_id: string;
      page_no: number;
    }>;
    web_used?: Array<{
      title: string;
      url: string;
      favicon: string | null;
    }>;
    charts_used?: Array<{
      chart_id: string;
      title: string;
      description?: string;
      chart_type: string;
      x_key?: string;
      y_keys?: string[];
      row_count?: number;
      item_url: string;
      download_json_url?: string;
      download_csv_url?: string;
    }>;
    sql_used?: SQLExecutionSource[];
  };
}

// Mind map types
export interface MindMapNode {
  id: string;
  title: string;
  description?: string | null;
  parent_id?: string | null;
  children: MindMapNode[];
}

export interface GlobalMindMap {
  user_id: string;
  thread_id: string;
  roots: MindMapNode[];
}

export interface MindMapResponse {
  mind_map: boolean;
  status?: boolean; // only present when mind_map is true
  message: string;
  data?: GlobalMindMap; // present when mind_map && status
}

export interface SummaryResponse {
  status?: boolean;
  summary?: string;
  message?: string;
  error?: string;
  failed?: boolean;
}

// Roadmap types (mirror backend Pydantic models)
export interface VisionAndEndGoal {
  description: string;
  success_criteria: string[];
}

export interface SWOT {
  strengths: string[];
  weaknesses: string[];
  opportunities: string[];
  threats: string[];
}

export interface CurrentBaseline {
  summary: string;
  swot: SWOT;
}

export interface StrategicPillar {
  pillar_name: string;
  description: string;
}

export interface PhasedRoadmapItem {
  phase: string;
  time_frame: string;
  key_objectives: string[];
  key_initiatives: string[];
  expected_outcomes: string[];
}

export interface EnablersAndDependencies {
  technologies: string[];
  skills_and_resources: string[];
  stakeholders: string[];
}

export interface RiskAndMitigation {
  risk: string;
  mitigation_strategy: string;
}

export interface KeyMetricsAndMilestone {
  year_or_phase: string;
  metrics: string[];
}

export interface LLMInferredAddition {
  section_title: string;
  content: string;
}

export interface StrategicRoadmapLLMOutput {
  roadmap_title: string;
  vision_and_end_goal: VisionAndEndGoal;
  current_baseline: CurrentBaseline;
  strategic_pillars: StrategicPillar[];
  phased_roadmap: PhasedRoadmapItem[];
  enablers_and_dependencies: EnablersAndDependencies;
  risks_and_mitigation: RiskAndMitigation[];
  key_metrics_and_milestones: KeyMetricsAndMilestone[];
  future_opportunities: string[];
  llm_inferred_additions: LLMInferredAddition[];
}

export interface StrategicRoadmapResponse {
  status?: boolean;
  strategic_roadmap?: StrategicRoadmapLLMOutput;
  message?: string;
  error?: string;
  failed?: boolean;
}

// Technical Roadmap types (mirror backend Pydantic models provided)
export interface OverallVision {
  goal: string;
  success_metrics: string[];
}

export interface CurrentStateAnalysis {
  summary: string;
  key_challenges: string[];
  existing_capabilities: string[];
}

export interface TechnologyDomain {
  domain_name: string;
  description: string;
}

export interface Initiative {
  initiative: string;
  objective: string;
  expected_outcome: string;
}

export interface PhasedRoadmapPhase {
  time_frame: string;
  focus_areas: string[];
  key_initiatives: Initiative[];
  dependencies: string[];
}

export interface PhasedRoadmap {
  short_term: PhasedRoadmapPhase;
  mid_term: PhasedRoadmapPhase;
  long_term: PhasedRoadmapPhase;
}

export interface KeyTechnologyEnabler {
  enabler: string;
  impact: string;
}

export interface RiskAndMitigationItem {
  risk: string;
  mitigation: string;
}

export interface InnovationOpportunity {
  idea: string;
  description: string;
  maturity_level: string;
}

export interface TabularSummaryRow {
  time_frame: string;
  key_points: string[];
}

export interface LLMInferredAddition {
  section_title: string;
  content: string;
}

export interface TechnicalRoadmapLLMOutput {
  roadmap_title: string;
  overall_vision: OverallVision;
  current_state_analysis: CurrentStateAnalysis;
  technology_domains: TechnologyDomain[];
  phased_roadmap: PhasedRoadmap;
  key_technology_enablers: KeyTechnologyEnabler[];
  risks_and_mitigations: RiskAndMitigationItem[];
  innovation_opportunities: InnovationOpportunity[];
  tabular_summary: TabularSummaryRow[];
  llm_inferred_additions?: LLMInferredAddition[] | null;
}

export interface TechnicalRoadmapResponse {
  status?: boolean;
  technical_roadmap?: TechnicalRoadmapLLMOutput;
  message?: string;
  error?: string;
  failed?: boolean;
}

// Insights types (mirror backend Pydantic models)
export interface DocumentSummary {
  title: string;
  purpose: string;
  key_themes: string[];
}

export interface KeyDiscussionPoint {
  topic: string;
  details: string;
}

export interface StrengthItem {
  aspect: string;
  evidence_or_example: string;
}

export interface ImprovementOrMissingArea {
  gap: string;
  suggested_improvement: string;
}

export interface FutureConsideration {
  focus_area: string;
  recommendation: string;
}

export interface InnovationAspect {
  innovation_title: string;
  description: string;
  potential_impact: string;
}

export interface PseudocodeOrTechnicalOutline {
  section?: string | null;
  pseudocode?: string | null;
}

export interface InsightsLLMOutput {
  document_summary: DocumentSummary;
  key_discussion_points: KeyDiscussionPoint[];
  strengths: StrengthItem[];
  improvement_or_missing_areas: ImprovementOrMissingArea[];
  future_considerations: FutureConsideration[];
  innovation_aspects: InnovationAspect[];
  pseudocode_or_technical_outline?: PseudocodeOrTechnicalOutline[] | null;
  llm_inferred_additions?: LLMInferredAddition[] | null;
}

export interface InsightsResponse {
  status?: boolean;
  insights?: InsightsLLMOutput;
  message?: string;
  error?: string;
  failed?: boolean;
}

// Strategic Analysis types (mirror backend Pydantic models)
export interface StrategicIntent {
  vision_statement: string;
  stated_objectives: string[];
  implicit_aspirations: string[];
}

export interface StrategicPositioning {
  current_position: string;
  target_position: string;
  competitive_landscape: string;
}

export interface StrategicTheme {
  theme: string;
  description: string;
  evidence_from_document: string;
}

export interface StakeholderInsight {
  stakeholder: string;
  role_or_interest: string;
  influence_level: string;
}

export interface ResourceAndCapability {
  resource: string;
  current_state: string;
  strategic_relevance: string;
}

export interface IdentifiedRisk {
  risk: string;
  severity: string;
  context: string;
}

export interface ForwardLookingAssessment {
  opportunities: string[];
  recommended_next_steps: string[];
  potential_challenges: string[];
  overall_assessment: string;
}

export interface StrategicAnalysisLLMOutput {
  analysis_title: string;
  executive_overview: string;
  strategic_intent: StrategicIntent;
  strategic_positioning: StrategicPositioning;
  key_strategic_themes: StrategicTheme[];
  stakeholder_insights: StakeholderInsight[];
  resources_and_capabilities: ResourceAndCapability[];
  identified_risks: IdentifiedRisk[];
  strategic_gaps_and_observations: string[];
  forward_looking_assessment: ForwardLookingAssessment;
  llm_inferred_additions?: LLMInferredAddition[] | null;
}

export interface StrategicAnalysisResponse {
  status?: boolean;
  strategic_analysis?: StrategicAnalysisLLMOutput;
  message?: string;
  error?: string;
  failed?: boolean;
}

// Technical Analysis types (mirror backend Pydantic models)
export interface TechnicalScope {
  domains_covered: string[];
  technology_stack: string[];
  architecture_overview: string;
}

export interface TechnicalDecision {
  decision: string;
  rationale: string;
  implications: string;
}

export interface TechnicalStrength {
  aspect: string;
  evidence: string;
}

export interface TechnicalConcern {
  concern: string;
  impact: string;
  evidence: string;
}

export interface TechnicalInnovation {
  element: string;
  description: string;
  maturity: string;
}

export interface TechnicalAspirations {
  stated_goals: string[];
  implied_direction: string;
  alignment_assessment: string;
}

export interface ImplementationReadiness {
  ready_components: string[];
  gaps_to_address: string[];
  dependencies: string[];
}

export interface TechnicalForwardAssessment {
  scalability_outlook: string;
  technology_evolution: string;
  recommended_focus_areas: string[];
  overall_assessment: string;
}

export interface TechnicalAnalysisLLMOutput {
  analysis_title: string;
  executive_overview: string;
  technical_scope: TechnicalScope;
  technical_decisions: TechnicalDecision[];
  technical_strengths: TechnicalStrength[];
  technical_concerns: TechnicalConcern[];
  innovation_elements: TechnicalInnovation[];
  technical_aspirations: TechnicalAspirations;
  implementation_readiness: ImplementationReadiness;
  forward_looking_assessment: TechnicalForwardAssessment;
  llm_inferred_additions?: LLMInferredAddition[] | null;
}

export interface TechnicalAnalysisResponse {
  status?: boolean;
  technical_analysis?: TechnicalAnalysisLLMOutput;
  message?: string;
  error?: string;
  failed?: boolean;
}

// ── Excel Skill types ──

export interface ExcelSkillGenerateResponse {
  status: boolean;
  message?: string;
  tracking_id?: string;
}

export interface ExcelSkillStatusResponse {
  status: boolean;
  message?: string;
  failed?: boolean;
  error?: string;
  result?: {
    file_name: string;
    download_url: string;
    description: string;
    sheet_count: number;
    total_rows: number;
  };
}

export interface ExcelSkillListItem {
  tracking_id: string;
  file_name: string;
  download_url: string;
  description: string;
  sheet_count: number;
  total_rows: number;
  created_at: string;
  request_text: string;
}

// ── Chart Skill types ──

export interface ChartSkillGenerateResponse {
  status: boolean;
  message?: string;
  tracking_id?: string;
}

export interface ChartSkillStatusResponse {
  status: boolean;
  message?: string;
  failed?: boolean;
  error?: string;
  result?: ChartSkillListItem;
}

export interface ChartSkillListItem {
  tracking_id: string;
  chart_id: string;
  title: string;
  description: string;
  chart_type: string;
  x_key: string;
  y_keys: string[];
  row_count: number;
  item_url: string;
  download_json_url: string;
  download_csv_url?: string | null;
  created_at: string;
  request_text: string;
}

export interface ChartSkillItemResponse {
  status: boolean;
  chart: {
    chart_id: string;
    title: string;
    description: string;
    chart_type: string;
    x_key: string;
    y_keys: string[];
    row_count: number;
    created_at: string;
    request_text: string;
    data: Array<Record<string, string | number | null>>;
  };
}

// Auth helpers
export const getAuthToken = () => localStorage.getItem('auth_token');
export const setAuthToken = (token: string) => localStorage.setItem('auth_token', token);
export const removeAuthToken = () => localStorage.removeItem('auth_token');
export const getCurrentUser = (): User | null => {
  const userStr = localStorage.getItem('current_user');
  return userStr ? JSON.parse(userStr) : null;
};
export const setCurrentUser = (user: User) => localStorage.setItem('current_user', JSON.stringify(user));
export const removeCurrentUser = () => localStorage.removeItem('current_user');

// API functions
export const api = {
  async register(name: string, email: string, password: string) {
    const response = await fetch(`${API_URL}/user/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });
    return response;
  },

  async login(email: string, password: string): Promise<LoginResponse> {
    const response = await fetch(`${API_URL}/user/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      const errorMessage = errorData.detail || 'Invalid email or password';
      throw new Error(errorMessage);
    }

    return response.json();
  },

  async getUser(userId: string): Promise<User> {
    const token = getAuthToken();
    console.log("Using token:", token);
    console.log("Fetching user with ID:", userId);
    const response = await fetch(`${API_URL}/user/${userId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    return data.user;
  },

  async uploadFiles(data: { thread_name?: string; thread_id?: string; files: File[] }): Promise<UploadResponse> {
    const token = getAuthToken();
    const formData = new FormData();

    if (data.thread_name) formData.append('thread_name', data.thread_name);
    if (data.thread_id) formData.append('thread_id', data.thread_id);
    data.files.forEach(file => formData.append('files', file));

    const response = await fetch(`${API_URL}/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });

    const json = await response.json();

    if (!response.ok || json.error) {
      const errorMessage = json.error || json.detail || 'Failed to upload files';
      throw new Error(errorMessage);
    }

    return json;
  },


  async uploadFilesWithProgress(params: {
    thread_name?: string;
    thread_id?: string;
    files: File[];
    onProgress?: (args: { fileIndex: number; loaded: number; total: number; percent: number }) => void;
  }): Promise<UploadResponse> {
    const token = getAuthToken();

    const uploadSingle = (file: File): Promise<UploadResponse> => {
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API_URL}/upload`, true);
        if (token) {
          xhr.setRequestHeader('Authorization', `Bearer ${token}`);
        }

        xhr.onload = () => {
          try {
            const json = JSON.parse(xhr.responseText);
            resolve(json);
          } catch (e) {
            reject(e);
          }
        };

        xhr.onerror = () => reject(new Error('Network error during upload'));

        const formData = new FormData();
        if (params.thread_name) formData.append('thread_name', params.thread_name);
        if (params.thread_id) formData.append('thread_id', params.thread_id);
        formData.append('files', file);

        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable && params.onProgress) {
            const percent = Math.round((event.loaded / event.total) * 100);
          }
        };

        xhr.send(formData);
      });
    };

    const results: UploadResponse = {
      status: 'success',
      message: 'Uploaded',
      thread_id: params.thread_id || '',
      documents: [],
    };

    for (let i = 0; i < params.files.length; i++) {
      const file = params.files[i];
      await new Promise<UploadResponse>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API_URL}/upload`, true);
        if (token) {
          xhr.setRequestHeader('Authorization', `Bearer ${token}`);
        }

        xhr.onload = () => {
          try {
            const json: UploadResponse = JSON.parse(xhr.responseText);

            // Check for errors in response
            if (xhr.status >= 400 || (json as any).error) {
              const errorMessage = (json as any).error || (json as any).detail || 'Failed to upload file';
              reject(new Error(errorMessage));
              return;
            }

            if (!results.thread_id && json.thread_id) {
              results.thread_id = json.thread_id;
            }
            results.documents = [...results.documents, ...json.documents];
            resolve(json);
          } catch (e) {
            reject(e);
          }
        };

        xhr.onerror = () => reject(new Error('Network error during upload'));

        const formData = new FormData();
        if (params.thread_name) formData.append('thread_name', params.thread_name);
        if (params.thread_id) formData.append('thread_id', params.thread_id);
        formData.append('files', file);

        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable && params.onProgress) {
            const percent = Math.round((event.loaded / event.total) * 100);
            params.onProgress({ fileIndex: i, loaded: event.loaded, total: event.total, percent });
          }
        };

        xhr.send(formData);
      });
    }

    return results;
  },

  async getThread(threadId: string): Promise<Thread> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/thread/${threadId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();

    if (!response.ok || data.error) {
      const errorMessage = data.error || data.detail || 'Failed to load thread';
      throw new Error(errorMessage);
    }

    return data.thread;
  },

  async query(
    threadId: string,
    question: string,
    mode: 'Internal' | 'External',
    useSelfKnowledge: boolean,
    useContext: boolean = false
  ): Promise<QueryResponse> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        thread_id: threadId,
        question,
        mode,
        use_self_knowledge: useSelfKnowledge,
        use_context: useContext,
      }),
    });

    const data = await response.json();

    if (!response.ok || data.error) {
      const errorMessage = data.error || data.detail || 'Failed to get response';
      throw new Error(errorMessage);
    }

    return data;
  },

  async deleteThread(threadId: string): Promise<{ status: boolean }> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/thread/${threadId}`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    return response.json();
  },

  async deleteDocument(threadId: string, docId: string): Promise<DeleteDocumentResponse> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/thread/${threadId}/document/${docId}`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const errorData = await response.json();
      const errorMessage = errorData.error || errorData.detail || 'Failed to delete document';
      throw new Error(errorMessage);
    }

    return response.json();
  },

  async addExistingDocument(
    targetThreadId: string,
    sourceThreadId: string,
    docId: string,
  ): Promise<AddExistingDocumentResponse> {
    const token = getAuthToken();
    const response = await fetch(
      `${API_URL}/thread/${targetThreadId}/documents/add-existing`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          source_thread_id: sourceThreadId,
          doc_id: docId,
        }),
      },
    );

    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error || data.detail || 'Failed to add document');
    }
    return data;
  },

  async updateThread(threadId: string, data: { thread_name: string }): Promise<{ status: string; message: string; thread_id: string; thread_name: string }> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/thread/${threadId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    });

    return response.json();
  },

  async deleteChat(threadId: string, chatIndex: number): Promise<DeleteChatResponse> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/thread/${threadId}/chats/${chatIndex}`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const errorData = await response.json();
      const errorMessage = errorData.error || errorData.detail || 'Failed to delete chat';
      throw new Error(errorMessage);
    }

    return response.json();
  },

  async clearThreadChats(threadId: string): Promise<ClearChatsResponse> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/thread/${threadId}/chats`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const errorData = await response.json();
      const errorMessage = errorData.error || errorData.detail || 'Failed to clear chats';
      throw new Error(errorMessage);
    }

    return response.json();
  },

  async getMindMap(threadId: string): Promise<MindMapResponse> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/mindmap/${threadId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      // Fallback shape with mind_map=false so UI can display error message
      return { mind_map: false, message: `Failed to fetch mind map (${response.status})` };
    }
    return response.json();
  },

  async generateMindMap(threadId: string, regenerate: boolean = false): Promise<MindMapResponse> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/mindmap/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ thread_id: threadId, regenerate }),
    });

    let data: any = null;
    try {
      data = await response.json();
    } catch {
      return { mind_map: false, message: `Failed to trigger mind map generation (${response.status})` };
    }

    if (!response.ok) {
      return {
        mind_map: false,
        message: data?.error || data?.detail || data?.message || 'Failed to trigger mind map generation',
      };
    }

    return data as MindMapResponse;
  },

  async summary(threadId: string, documentId: string, regenerate: boolean = false): Promise<SummaryResponse> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/summary`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ thread_id: threadId, document_id: documentId, regenerate }),
    });
    let data: any = null;
    try {
      data = await response.json();
    } catch (_) {
      return { status: false, error: `Failed to parse summary response (${response.status})` };
    }
    if (!response.ok) {
      // Normalize error shape
      return { status: false, error: data?.detail || data?.message || 'Summary request failed' };
    }
    return data as SummaryResponse;
  },

  async summaryGlobal(threadId: string, regenerate: boolean = false): Promise<SummaryResponse> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/summary/global`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ thread_id: threadId, regenerate }),
    });
    let data: any = null;
    try {
      data = await response.json();
    } catch (_) {
      return { status: false, error: `Failed to parse summary (global) response (${response.status})` };
    }
    if (!response.ok) {
      return { status: false, error: data?.detail || data?.message || 'Summary (global) request failed' };
    }
    return data as SummaryResponse;
  },

  // ── Thread Instructions ──

  async getInstructions(threadId: string): Promise<ThreadInstruction[]> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/thread/${threadId}/instructions`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error || 'Failed to load instructions');
    }
    return data.instructions ?? [];
  },

  async addInstruction(threadId: string, text: string): Promise<ThreadInstruction> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/thread/${threadId}/instructions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ text }),
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error || 'Failed to add instruction');
    }
    return data.instruction;
  },

  async updateInstruction(
    threadId: string,
    instructionId: string,
    updates: { text?: string; selected?: boolean }
  ): Promise<ThreadInstruction> {
    const token = getAuthToken();
    const response = await fetch(
      `${API_URL}/thread/${threadId}/instructions/${instructionId}`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(updates),
      }
    );
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error || 'Failed to update instruction');
    }
    return data.instruction;
  },

  async deleteInstruction(threadId: string, instructionId: string): Promise<void> {
    const token = getAuthToken();
    const response = await fetch(
      `${API_URL}/thread/${threadId}/instructions/${instructionId}`,
      {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error || 'Failed to delete instruction');
    }
  },

  // ── Settings ──

  async getSwitches(): Promise<{ switches: Record<string, boolean> }> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/settings/switches`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to fetch switches');
    }
    return data;
  },

  async updateSwitch(key: string, value: boolean): Promise<{ key: string; value: boolean }> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/settings/switches/${key}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ value }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to update switch');
    }
    return data;
  },

  // ── Excel Skill ──

  async excelSkillGenerate(
    threadId: string,
    requestText: string,
    sourceDocumentIds?: string[],
  ): Promise<ExcelSkillGenerateResponse> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/excel-skill/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        thread_id: threadId,
        request_text: requestText,
        source_document_ids: sourceDocumentIds || null,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || 'Failed to start Excel generation');
    }
    return data;
  },

  async excelSkillStatus(
    trackingId: string,
  ): Promise<ExcelSkillStatusResponse> {
    const token = getAuthToken();
    const response = await fetch(
      `${API_URL}/excel-skill/status/${trackingId}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || 'Failed to check Excel status');
    }
    return data;
  },

  async excelSkillDownload(
    threadId: string,
    filename: string,
  ): Promise<Blob> {
    const token = getAuthToken();
    const response = await fetch(
      `${API_URL}/excel-skill/download/${threadId}/${filename}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (!response.ok) {
      throw new Error('Failed to download Excel file');
    }
    return response.blob();
  },

  async excelSkillList(
    threadId: string,
  ): Promise<{ files: ExcelSkillListItem[] }> {
    const token = getAuthToken();
    const response = await fetch(
      `${API_URL}/excel-skill/list/${threadId}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to list Excel files');
    }
    return data;
  },

  async excelSkillDelete(
    threadId: string,
    trackingId: string,
  ): Promise<void> {
    const token = getAuthToken();
    const response = await fetch(
      `${API_URL}/excel-skill/${threadId}/${trackingId}`,
      { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } },
    );
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || 'Failed to delete Excel file');
    }
  },

  // ── Chart Skill ──

  async chartSkillGenerate(
    threadId: string,
    requestText: string,
    chartType?: string,
    sourceDocumentIds?: string[],
  ): Promise<ChartSkillGenerateResponse> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/chart-skill/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        thread_id: threadId,
        request_text: requestText,
        chart_type: chartType || null,
        source_document_ids: sourceDocumentIds || null,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || 'Failed to start chart generation');
    }
    return data;
  },

  async chartSkillStatus(trackingId: string): Promise<ChartSkillStatusResponse> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/chart-skill/status/${trackingId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || 'Failed to check chart status');
    }
    return data;
  },

  async chartSkillList(threadId: string): Promise<{ charts: ChartSkillListItem[] }> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/chart-skill/list/${threadId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || 'Failed to list charts');
    }
    return data;
  },

  async chartSkillItem(threadId: string, chartId: string): Promise<ChartSkillItemResponse> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/chart-skill/item/${threadId}/${chartId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || 'Failed to fetch chart');
    }
    return data;
  },

  async chartSkillDelete(threadId: string, trackingId: string): Promise<void> {
    const token = getAuthToken();
    const response = await fetch(`${API_URL}/chart-skill/${threadId}/${trackingId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || data.error || 'Failed to delete chart');
    }
  },
};

// WebSocket helper
export const getWebSocketUrl = (path: string) => {
  // Allow explicit WS base via env, otherwise derive from API_URL
  const base = (import.meta.env.VITE_WS_URL as string | undefined) || API_URL;
  const url = new URL(base);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  // Ensure we don't double up slashes
  const joined = `${url.origin}${path.startsWith('/') ? '' : '/'}${path}`;
  return joined;
};
