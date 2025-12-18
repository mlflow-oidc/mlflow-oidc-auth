import { useNavigate } from "react-router";
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
                <button
                    onClick={() => navigate("/user")}
                    className="
            px-4 py-2 rounded-md font-medium transition-colors duration-200
            bg-btn-primary dark:bg-btn-primary-dark
            text-btn-primary-text dark:text-btn-primary-text-dark
            hover:bg-btn-primary-hover dark:hover:bg-btn-primary-hover-dark
            shadow-md cursor-pointer
          "
                >
                    Go to My Profile
                </button>
            </div>
        </PageContainer>
    );
};

export default NotFoundPage;
