"use client";

import { TenantForm } from "@/components/TenantForm";
import { PageHeader } from "@/components/ui";

export default function NewTenantPage() {
  return (
    <div>
      <PageHeader title="Add tenant" subtitle="Documents (ID proof, photo) can be uploaded after saving." />
      <TenantForm />
    </div>
  );
}
