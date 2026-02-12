import { useParams } from "react-router";
import { useExperimentUserPermissions } from "../../core/hooks/use-experiment-user-permissions";
import { useExperimentGroupPermissions } from "../../core/hooks/use-experiment-group-permissions";
import { useAllExperiments } from "../../core/hooks/use-all-experiments";
import { EntityPermissionsPageLayout } from "../permissions/components/entity-permissions-page-layout";

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

  const { allExperiments } = useAllExperiments();

  if (!experimentId) {
    return <div>Experiment ID is required.</div>;
  }

  const experiment = allExperiments?.find((e) => e.id === experimentId);
  const experimentName = experiment?.name || experimentId;

  return (
    <EntityPermissionsPageLayout
      title={`Permissions for Experiment ${experimentName}`}
      resourceId={experimentId}
      resourceName={experimentName}
      resourceType="experiments"
      userPermissions={experimentUserPermissions}
      groupPermissions={experimentGroupPermissions}
      isLoading={isLoading}
      error={error}
      refresh={refresh}
    />
  );
}
