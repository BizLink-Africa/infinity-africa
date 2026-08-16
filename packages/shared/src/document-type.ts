/** Compliance documents required during merchant onboarding. */
export enum DocumentType {
  NIDA = "NIDA",
  TIN_CERTIFICATE = "TIN_CERTIFICATE",
  BUSINESS_LICENCE = "BUSINESS_LICENCE",
}

export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  [DocumentType.NIDA]: "NIDA",
  [DocumentType.TIN_CERTIFICATE]: "TIN Certificate",
  [DocumentType.BUSINESS_LICENCE]: "Business Licence",
};

export type DocumentUploadStatus = "UPLOADED" | "VERIFIED" | "REJECTED";

export const DOCUMENT_UPLOAD_STATUS_LABELS: Record<DocumentUploadStatus, string> = {
  UPLOADED: "Pending Review",
  VERIFIED: "Verified",
  REJECTED: "Rejected",
};
