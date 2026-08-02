import { z } from "zod";

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const ACCEPTED_FILE_TYPES = [
  "text/csv",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/pdf",
];

export const uploadDatasetSchema = z.object({
  file: z.any()
    .refine((file) => file instanceof File, "Please upload a valid file.")
    .refine((file) => file.size <= MAX_FILE_SIZE, "File size must not exceed 50MB.")
    .refine(
      (file) => ACCEPTED_FILE_TYPES.includes(file.type),
      "Only CSV, Excel, and PDF files are supported."
    ),
  tableName: z.string()
    .min(2, "Table name must be at least 2 characters.")
    .regex(/^[a-zA-Z_][a-zA-Z0-9_]*$/, "Table name must contain only alphanumeric characters or underscores, and cannot start with a number."),
});

export type UploadDatasetInput = z.infer<typeof uploadDatasetSchema>;
