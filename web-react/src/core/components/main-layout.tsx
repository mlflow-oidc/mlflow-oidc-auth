import React, { useState, type ReactNode } from "react";
import Header from "../../shared/components/header";
import Sidebar from "../../shared/components/sidebar";
import { useUser } from "../hooks/use-user";

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

  const { currentUser } = useUser();

  const userName =
    currentUser?.display_name || currentUser?.username || "Guest";

  const sidebarWidthClass = isSidebarOpen
    ? SIDEBAR_WIDTH_OPEN_CLASS
    : SIDEBAR_WIDTH_CLOSED_CLASS;

  return (
    <div className="flex flex-col h-screen overflow-hidden relative bg-ui-secondary-bg dark:bg-ui-secondary-bg-dark">
      <Header userName={userName} />
      <main className="flex flex-1 overflow-hidden">
        <Sidebar
          currentUser={currentUser}
          isOpen={isSidebarOpen}
          toggleSidebar={toggleSidebar}
          widthClass={sidebarWidthClass}
        />
        <div className="flex flex-col flex-1 overflow-hidden p-4 rounded-xl shadow-xl bg-ui-bg text-ui-text dark:bg-ui-bg-dark dark:text-ui-text-dark">
          {children}
        </div>
      </main>
    </div>
  );
};

export default MainLayout;
