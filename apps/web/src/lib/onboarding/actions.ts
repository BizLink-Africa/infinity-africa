"use server";

import { redirect } from "next/navigation";

import { DocumentType, ServiceNeeded } from "@infinity/shared";

import { getCurrentUser } from "@/lib/auth/current-user";
import type { FormState } from "@/lib/auth/form-state";

import { OnboardingApiError, submitOnboardingAccount, uploadOnboardingDocument } from "./api";

const ALLOWED_DOCUMENT_TYPES = new Set(["application/pdf", "image/jpeg", "image/png"]);
const VALID_SERVICES = new Set<string>(Object.values(ServiceNeeded));

function validateDocument(
  file: FormDataEntryValue | null,
  errors: Record<string, string[]>,
  field: string,
  label: string,
): File | null {
  if (!(file instanceof File) || file.size === 0 || !file.name) {
    errors[field] = [`${label} is required.`];
    return null;
  }
  if (!ALLOWED_DOCUMENT_TYPES.has(file.type)) {
    errors[field] = [`${label} must be a PDF, JPG, or PNG file.`];
    return null;
  }
  return file;
}

export async function submitOnboardingAction(_prevState: FormState, formData: FormData): Promise<FormState> {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/merchant/login");
  }

  const businessName = String(formData.get("businessName") ?? "").trim();
  const natureOfBusiness = String(formData.get("natureOfBusiness") ?? "").trim();
  const businessCategory = String(formData.get("businessCategory") ?? "").trim();
  const physicalAddress = String(formData.get("physicalAddress") ?? "").trim();
  const regionCity = String(formData.get("regionCity") ?? "").trim();
  const websiteOrAppLink = String(formData.get("websiteOrAppLink") ?? "").trim();

  const servicesNeeded = formData
    .getAll("servicesNeeded")
    .map((v) => String(v))
    .filter((v): v is ServiceNeeded => VALID_SERVICES.has(v));

  const agreedToTerms = formData.get("agreedToTerms") === "on";
  const agreedToPrivacy = formData.get("agreedToPrivacy") === "on";
  const confirmedAccurate = formData.get("confirmedAccurate") === "on";

  const errors: Record<string, string[]> = {};
  if (!businessName) errors.businessName = ["Business name is required."];
  if (!natureOfBusiness) errors.natureOfBusiness = ["Nature of business is required."];
  if (!businessCategory) errors.businessCategory = ["Business category is required."];
  if (!physicalAddress) errors.physicalAddress = ["Physical address is required."];
  if (!regionCity) errors.regionCity = ["Region/city is required."];
  if (servicesNeeded.length === 0) errors.servicesNeeded = ["Select at least one service you need."];

  const nidaFile = validateDocument(formData.get("nidaDocument"), errors, "nidaDocument", "NIDA upload");
  const tinFile = validateDocument(formData.get("tinDocument"), errors, "tinDocument", "TIN certificate upload");
  const licenceFile = validateDocument(formData.get("licenceDocument"), errors, "licenceDocument", "Business licence upload");

  if (!agreedToTerms) errors.agreedToTerms = ["You must agree to the Infinity Africa Terms of Service."];
  if (!agreedToPrivacy) errors.agreedToPrivacy = ["You must agree to the Infinity Africa Privacy Policy."];
  if (!confirmedAccurate) errors.confirmedAccurate = ["You must confirm the information provided is accurate."];

  const values = { businessName, natureOfBusiness, businessCategory, physicalAddress, regionCity, websiteOrAppLink };

  if (Object.keys(errors).length > 0) {
    return { errors, values };
  }

  try {
    await submitOnboardingAccount({
      business_name: businessName,
      nature_of_business: natureOfBusiness,
      business_category: businessCategory,
      physical_address: physicalAddress,
      region_city: regionCity,
      website_url: websiteOrAppLink || null,
      contact_phone: user.phone,
      services_needed: servicesNeeded,
      accepted_terms: agreedToTerms,
      accepted_privacy: agreedToPrivacy,
    });

    await Promise.all([
      uploadOnboardingDocument(DocumentType.NIDA, nidaFile as File),
      uploadOnboardingDocument(DocumentType.TIN_CERTIFICATE, tinFile as File),
      uploadOnboardingDocument(DocumentType.BUSINESS_LICENCE, licenceFile as File),
    ]);
  } catch (err) {
    const formError =
      err instanceof OnboardingApiError
        ? err.code === "conflict"
          ? "You already have a merchant account submitted for review."
          : err.message
        : "Couldn't reach Infinity Africa. Check your connection and try again.";
    return { errors: {}, formError, values };
  }

  redirect("/merchant/overview");
}
