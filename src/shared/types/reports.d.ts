export interface Report {
  id: string;
  title: string;
  type: "PDF" | "PowerPoint" | "CSV";
  frequency: "Daily" | "Weekly" | "Ad-hoc";
  created: string;
  size: string;
  recipient: string;
}

export interface Invoice {
  invoiceId: string;
  amount: string;
  date: string;
  status: "Paid" | "Pending";
}

export interface NotificationLog {
  id: string;
  title: string;
  description: string;
  date: string;
  read: boolean;
}
