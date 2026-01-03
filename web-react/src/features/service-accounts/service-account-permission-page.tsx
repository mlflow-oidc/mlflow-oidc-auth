import PageContainer from "../../shared/components/page/page-container";
import { useParams } from "react-router";

export default function ServiceAccountPermissionPage() {
  const { username } = useParams<{ username: string }>();

  return (
    <PageContainer title={`Permissions for ${username}`}>
      <div className="p-4">
        <p>Service Account Permission Page Placeholder for {username}</p>
      </div>
    </PageContainer>
  );
}
