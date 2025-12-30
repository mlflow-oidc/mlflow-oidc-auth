import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import { useExperimentUserPermissions } from "../../core/hooks/use-experiment-user-permissions";
import { useAllExperiments } from "../../core/hooks/use-all-experiments";
import { EntityPermissionsManager } from "../permissions/components/entity-permissions-manager";

export default function ExperimentPermissionsPage() {
  const { experimentId: routeExperimentId } = useParams<{
    experimentId: string;
  }>();

  const experimentId = routeExperimentId || null;

  const { isLoading, error, refresh, experimentUserPermissions } =
    useExperimentUserPermissions({ experimentId });

  const { allExperiments } = useAllExperiments();

  if (!experimentId) {
    return <div>Experiment ID is required.</div>;
  }

  const experiment = allExperiments?.find((e) => e.id === experimentId);
  const experimentName = experiment?.name || experimentId;

  return (
    <PageContainer title={`Permissions for Experiment ${experimentName}`}>
      <EntityPermissionsManager
        resourceId={experimentId}
        resourceType="experiments"
        permissions={experimentUserPermissions || []}
        isLoading={isLoading}
        error={error}
        refresh={refresh}
      />
    </PageContainer>
  );
}
