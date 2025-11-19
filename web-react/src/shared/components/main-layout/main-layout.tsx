import React, { useState, type ReactNode } from "react";
import Header from "./header";
import Sidebar from "./sidebar";
import { useUserData } from "../../context/use-user-data";

interface MainLayoutProps {
  children: ReactNode;
}

const SIDEBAR_WIDTH_OPEN_CLASS = "w-[200px]";
const SIDEBAR_WIDTH_CLOSED_CLASS = "w-10";

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const toggleSidebar = () => {
    setIsSidebarOpen((prev) => !prev);
  };

  const { currentUser } = useUserData();

  const userName =
    currentUser?.display_name || currentUser?.username || "Guest";

  const sidebarWidthClass = isSidebarOpen
    ? SIDEBAR_WIDTH_OPEN_CLASS
    : SIDEBAR_WIDTH_CLOSED_CLASS;

  return (
    <div className="flex flex-col relative h-full bg-ui-secondary-bg dark:bg-ui-secondary-bg-dark">
      <Header userName={userName} />
      <main className="flex grow flex-row h-full ml-1">
        <Sidebar
          isOpen={isSidebarOpen}
          toggleSidebar={toggleSidebar}
          widthClass={sidebarWidthClass}
        />
        <div className="grow p-4 rounded-xl mr-3 ml-1 mb-3 shadow-xl bg-ui-bg text-ui-text dark:bg-ui-bg-dark dark:text-ui-text-dark">
          {children}
        </div>
      </main>
    </div>
  );
};

export default MainLayout;
