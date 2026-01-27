import { useNavigate } from "react-router";
import { Button } from "../../shared/components/button";
import PageContainer from "../../shared/components/page/page-container";

export const NotFoundPage = () => {
  const navigate = useNavigate();

  return (
    <PageContainer title="Page Not Found">
      <div className="flex flex-col items-center justify-center h-[50vh] space-y-6 text-center">
        <div className="space-y-2">
          <h1 className="text-4xl font-bold text-text-primary dark:text-text-primary-dark">
            404
          </h1>
          <p className="text-xl text-text-secondary dark:text-text-secondary-dark">
            Oops! The page you are looking for does not exist.
          </p>
        </div>
        <Button
          onClick={() => {
            void navigate("/user");
          }}
          variant="primary"
        >
          Go to My Profile
        </Button>
      </div>
    </PageContainer>
  );
};

export default NotFoundPage;
