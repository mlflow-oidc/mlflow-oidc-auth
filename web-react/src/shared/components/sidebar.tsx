import React from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faAnglesLeft } from "@fortawesome/free-solid-svg-icons";
import AppLink from "./app-link";
import { getSidebarData } from "./sidebar-data";
import { useUserData } from "../context/use-user-data";

interface SidebarProps {
  isOpen: boolean;
  toggleSidebar: () => void;
  widthClass: string;
}

const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  toggleSidebar,
  widthClass,
}) => {
  const { currentUser, isLoading } = useUserData();
  const isAdmin = currentUser?.is_admin ?? false;

  const sidebarData = getSidebarData(isAdmin);

  const ADMIN_LINKS_START_INDEX = 6;

  const baseSidebarClasses =
    "flex-shrink-0 mb-1 text-sm bg-ui-secondary-bg dark:bg-ui-secondary-bg-dark";

  if (isLoading) {
    return (
      <aside className={`${baseSidebarClasses} ${widthClass}`}>
        <div className="p-2 ml-2 text-btn-secondary-text dark:text-btn-secondary-text-dark"></div>
      </aside>
    );
  }
  return (
    <aside className={`${baseSidebarClasses} ${widthClass} overflow-y-auto`}>
      <div className="flex flex-col h-full">
        <nav className="flex flex-col space-y-1 flex-grow p-2">
          {sidebarData.map((link, index) => (
            <React.Fragment key={link.href}>
              {index === ADMIN_LINKS_START_INDEX && isAdmin && (
                <div className="my-2 border-t border-btn-secondary-border dark:border-btn-secondary-border-dark  pt-2" />
              )}

              <AppLink
                href={link.href}
                isInternalLink={link.isInternalLink}
                className={`
                  text-text-primary hover:text-text-primary-hover dark:text-text-primary-dark dark:hover:text-text-primary-hover-dark cursor-pointer
                  font-medium rounded-md transition-colors w-full p-0
                  ${isOpen ? "justify-start" : "justify-center"}
                `}
              >
                <div className="flex items-center p-1">
                  <span className={isOpen ? "w-5" : "w-full flex"}>
                    <FontAwesomeIcon icon={link.icon!} size="1x" />
                  </span>
                  <span
                    className={`
                      whitespace-nowrap
                      ${
                        isOpen
                          ? "opacity-100 max-w-xs ml-2"
                          : "opacity-0 max-w-0"
                      }
                    `}
                  >
                    {link.label}
                  </span>
                </div>
              </AppLink>
            </React.Fragment>
          ))}
        </nav>

        <div className="p-2 border-t border-btn-secondary-border dark:border-btn-secondary-border-dark ">
          <button
            type="button"
            onClick={toggleSidebar}
            className={`
              text-text-primary hover:text-text-primary-hover hover:bg-bg-primary-hover dark:text-text-primary-dark dark:hover:text-text-primary-hover-dark dark:hover:bg-bg-primary-hover-dark cursor-pointer p-1 rounded transition-colors flex items-center w-full
              ${isOpen ? "justify-end" : "justify-center"}
            `}
            aria-label={isOpen ? "Collapse Sidebar" : "Expand Sidebar"}
          >
            <FontAwesomeIcon
              icon={faAnglesLeft}
              className={`w-5 h-5 transition-transform duration-150 ${
                isOpen ? "rotate-0" : "rotate-180"
              }`}
            />
          </button>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
