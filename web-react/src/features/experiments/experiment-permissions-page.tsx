import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import { useExperimentUserPermissions } from "../../core/hooks/use-experiment-user-permissions";
import { useExperimentGroupPermissions } from "../../core/hooks/use-experiment-group-permissions";
import { useAllExperiments } from "../../core/hooks/use-all-experiments";
import { EntityPermissionsManager } from "../permissions/components/entity-permissions-manager";

export default function ExperimentPermissionsPage() {
  const { experimentId: routeExperimentId } = useParams<{
    experimentId: string;
  }>();

  const experimentId = routeExperimentId || null;

  const {
    isLoading: isUserLoading,
    error: userError,
    refresh: refreshUser,
    experimentUserPermissions,
  } = useExperimentUserPermissions({ experimentId });

  const {
    isLoading: isGroupLoading,
    error: groupError,
    refresh: refreshGroup,
    experimentGroupPermissions,
  } = useExperimentGroupPermissions({ experimentId });

  const isLoading = isUserLoading || isGroupLoading;
  const error = userError || groupError;
  const refresh = () => {
    refreshUser();
    refreshGroup();
  };

  const allPermissions = [
    ...(experimentUserPermissions || []),
    ...(experimentGroupPermissions || []),
  ];

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
        resourceName={experimentName}
        resourceType="experiments"
        permissions={allPermissions}
        isLoading={isLoading}
        error={error}
        refresh={refresh}
      />
    </PageContainer>
  );
}
