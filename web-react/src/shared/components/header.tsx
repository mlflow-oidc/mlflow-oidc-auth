import { useEffect, useState } from "react";
import { Link } from "react-router";
import DarkModeToggle from "./dark-mode-toggle";
import MenuIcon from "../icons/menu-icon";
import CloseIcon from "../icons/close-icon";
import { getNavigationData } from "./navigation-data";
import HeaderDesktopNav from "./header-desktop-nav";
import HeaderMobileNav from "./header-mobile-nav";
import { useRuntimeConfig } from "../context/use-runtime-config";

interface HeaderProps {
  userName?: string;
}

const Header: React.FC<HeaderProps> = ({ userName = "User" }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const handleLinkClick = () => setIsMenuOpen(false);
  const config = useRuntimeConfig();

  const navigationData = getNavigationData(userName, config.basePath);

  useEffect(() => {
    if (isMenuOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }

    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isMenuOpen]);

  return (
    <header className="p-2 shadow-md bg-ui-secondary-bg dark:bg-ui-secondary-bg-dark">
      <div className="sticky z-3 flex justify-between items-center">
        <Link to="/" className="text-xl font-extrabold text-logo">
          MlflowOidcAuth
        </Link>

        <div className="flex">
          <div className="flex items-center">
            <DarkModeToggle />
            <button
              type="button"
              className="sm:hidden fill-current text-text-primary hover:text-text-primary-hover hover:bg-bg-primary-hover dark:text-text-primary-dark dark:hover:text-text-primary-hover-dark dark:hover:bg-bg-primary-hover-dark cursor-pointer p-1 rounded transition-colors"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              aria-expanded={isMenuOpen}
              aria-controls="mobile-menu"
            >
              {isMenuOpen ? <CloseIcon /> : <MenuIcon />}
            </button>
          </div>

          <HeaderDesktopNav
            mainLinks={navigationData.mainLinks}
            userControls={navigationData.userControls}
          />
        </div>
      </div>

      <HeaderMobileNav
        isMenuOpen={isMenuOpen}
        onLinkClick={handleLinkClick}
        mainLinks={navigationData.mainLinks}
        userControls={navigationData.userControls}
      />
    </header>
  );
};

export default Header;
