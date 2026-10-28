"use client";

import { useParams } from "next/navigation";

import { TenantForm } from "@/components/TenantForm";
import { ErrorBox, Loading, PageHeader } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { TenantDetail } from "@/lib/types";

export default function EditTenantPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error } = useApi<TenantDetail>(`/api/tenants/${id}`);
  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading />;
  return (
    <div>
      <PageHeader title={`Edit ${data.name}`} />
      <TenantForm tenant={data} />
    </div>
  );
}
