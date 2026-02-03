import React from "react";
import { AppLink } from "./app-link";
import { getSidebarData } from "./sidebar-data";
import type { CurrentUser } from "../types/user";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faAnglesLeft, faHeart } from "@fortawesome/free-solid-svg-icons";
import { Button } from "./button";
import { useRuntimeConfig } from "../context/use-runtime-config";

interface SidebarProps {
  currentUser: CurrentUser | null;
  isOpen: boolean;
  toggleSidebar: () => void;
  widthClass: string;
}

const Sidebar: React.FC<SidebarProps> = ({
  currentUser,
  isOpen,
  toggleSidebar,
  widthClass,
}) => {
  const isAdmin = currentUser?.is_admin ?? false;
  const { gen_ai_gateway_enabled: genAiGatewayEnabled } = useRuntimeConfig();

  const sidebarData = getSidebarData(isAdmin, genAiGatewayEnabled);

  const BASE_LINKS_COUNT = 6;
  const AI_LINKS_COUNT = 3;

  const baseSidebarClasses =
    "flex-shrink-0 text-sm bg-ui-secondary-bg dark:bg-ui-secondary-bg-dark";

  return (
    <aside className={`${baseSidebarClasses} ${widthClass} overflow-y-auto`}>
      <div className="flex flex-col h-full">
        <nav className="flex flex-col space-y-1 grow p-2">
          {sidebarData.map((link, index) => {
            const isAiStart = genAiGatewayEnabled && index === BASE_LINKS_COUNT;
            const isAdminStart =
              isAdmin &&
              index ===
                (genAiGatewayEnabled
                  ? BASE_LINKS_COUNT + AI_LINKS_COUNT
                  : BASE_LINKS_COUNT);

            return (
              <React.Fragment key={link.href}>
                {(isAiStart || isAdminStart) && (
                  <div className="my-3 border-t border-btn-secondary-border dark:border-btn-secondary-border-dark pt-1" />
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
            );
          })}
          <AppLink
            href="https://github.com/sponsors/mlflow-oidc?o=esb"
            isInternalLink={false}
            className={`
              mt-auto
              text-text-primary hover:text-text-primary-hover dark:text-text-primary-dark dark:hover:text-text-primary-hover-dark cursor-pointer
              font-medium rounded-md transition-colors w-full p-0
              ${isOpen ? "justify-start" : "justify-center"}
            `}
          >
            <div className="flex items-center p-1">
              <span className={isOpen ? "w-5" : "w-full flex"}>
                <FontAwesomeIcon
                  icon={faHeart}
                  size="1x"
                  className="color-text-btn-secondary"
                />
              </span>
              <span
                className={`
                  whitespace-nowrap
                  ${isOpen ? "opacity-100 max-w-xs ml-2" : "opacity-0 max-w-0"}
                `}
              >
                Support the project
              </span>
            </div>
          </AppLink>
        </nav>

        <div className="p-2 border-t border-btn-secondary-border dark:border-btn-secondary-border-dark ">
          <Button
            variant="ghost"
            onClick={toggleSidebar}
            className={`w-full ${isOpen ? "justify-end" : "justify-center"}`}
            aria-label={isOpen ? "Collapse Sidebar" : "Expand Sidebar"}
            icon={faAnglesLeft}
            iconClassName={`w-5 h-5 transition-transform duration-150 ${
              isOpen ? "rotate-0" : "rotate-180"
            }`}
          />
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
