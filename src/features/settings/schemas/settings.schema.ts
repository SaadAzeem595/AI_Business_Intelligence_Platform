import { z } from "zod";

export const profileSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters."),
  email: z.string().email("Please enter a valid work email address."),
});

export type ProfileInput = z.infer<typeof profileSchema>;

export const workspaceSchema = z.object({
  name: z.string().min(2, "Workspace name must be at least 2 characters."),
  slug: z.string()
    .min(2, "Workspace slug must be at least 2 characters.")
    .regex(/^[a-z0-9-]+$/, "Slug must only contain lowercase alphanumeric letters and dashes."),
});

export type WorkspaceInput = z.infer<typeof workspaceSchema>;

export const billingSchema = z.object({
  cardNumber: z.string().regex(/^\d{16}$/, "Card number must be 16 digits."),
  expDate: z.string().regex(/^(0[1-9]|1[0-2])\/\d{2}$/, "Expiry date must be in MM/YY format."),
  cvc: z.string().regex(/^\d{3,4}$/, "CVC must be 3 or 4 digits."),
});

export type BillingInput = z.infer<typeof billingSchema>;
