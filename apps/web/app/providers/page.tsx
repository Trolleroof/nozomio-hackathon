import { AppFrame } from "@/components/app-frame";
import { ProviderMatrix } from "@/components/provider-matrix";
import { listProviderCapabilities } from "@/lib/crucible-data";

export default async function ProvidersPage() {
  const providerCapabilities = await listProviderCapabilities();

  return (
    <AppFrame>
      <div className="mb-8">
        <h1 className="text-2xl font-medium tracking-tight">Provider status</h1>
      </div>
      <ProviderMatrix providers={providerCapabilities} />
    </AppFrame>
  );
}
