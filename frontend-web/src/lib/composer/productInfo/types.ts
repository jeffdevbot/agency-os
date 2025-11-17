import type { ProductBrief } from "../../../../../lib/composer/types";

export interface FaqItem {
  question: string;
  answer?: string;
}

export interface FaqFormItem extends FaqItem {
  clientId: string;
}

export interface ProjectMetaPayload {
  projectName: string;
  clientName: string;
  marketplaces: string[];
  category: string | null;
  brandTone: string | null;
  whatNotToSay: string[] | null;
  productBrief: ProductBrief;
  suppliedInfo: Record<string, unknown>;
  faq: FaqItem[] | null;
}

export interface ProductInfoFormState {
  projectName: string;
  clientName: string;
  marketplaces: string[];
  category: string;
  brandTone: string;
  whatNotToSay: string[];
  productBrief: ProductBrief;
  suppliedInfoNotes: string;
  faq: FaqFormItem[];
}

export interface ProductInfoFormErrors {
  projectName?: string;
  clientName?: string;
  marketplaces?: string;
}
