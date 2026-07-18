export type Role = "employee" | "agent";
export type Status = "open" | "resolved";
export const CATEGORIES = ["IT", "HR", "Finance", "Admin", "Other"] as const;
export const PRIORITIES = ["Low", "Medium", "High"] as const;
export type Category = (typeof CATEGORIES)[number];
export type Priority = (typeof PRIORITIES)[number];

export interface User {
  id: number;
  email: string;
  role: Role;
}

export interface Ticket {
  id: number;
  title: string;
  description: string;
  attachment_filename: string | null;
  status: Status;
  category: Category;
  priority: Priority;
  ai_category: Category;
  ai_priority: Priority;
  ai_confidence: number | null;
  employee: User;
  created_at: string;
  updated_at: string;
}

export interface Reply {
  ai_draft: string;
  final_reply: string;
  citations: string[];
  sent_at: string;
}

export interface AuditEntry {
  id: number;
  field: string;
  old_value: string;
  new_value: string;
  agent: User;
  created_at: string;
}

export interface TicketDetail extends Ticket {
  reply: Reply | null;
  audit_log: AuditEntry[];
}

export interface Metrics {
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  median_resolution_seconds: number | null;
  category_override_rate: number;
  total_tickets: number;
}
