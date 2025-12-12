import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";

export default function ExperimentPermissionsPage() {
  const { experimentId } = useParams<{ experimentId: string }>();

  if (!experimentId) {
    return (
      <PageContainer title="Permissions Error">
        <p>Error: Experiment ID not provided.</p>
      </PageContainer>
    );
  }

  // TODO: Add logic here to fetch and manage permissions using fetchExperimentUserPermissions
  // and the useExperimentUserPermissions hook.

  return (
    <PageContainer title={`Permissions for Experiment ${experimentId}`}>
      <h2>Manage Permissions</h2>
      <p>
        This is the page where you can manage permissions for experiment{" "}
        <b>{experimentId}</b>.
      </p>
    </PageContainer>
  );
}
