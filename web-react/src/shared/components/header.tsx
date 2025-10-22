import { useEffect, useState } from "react";
import { Link } from "react-router";
import DarkModeToggle from "./dark-mode-toggle";
import MenuIcon from "../icons/menu-icon";
import CloseIcon from "../icons/close-icon";
import { getNavigationData } from "./navigation-data";
import HeaderDesktopNav from "./header-desktop-nav";
import HeaderMobileNav from "./header-mobile-nav";

interface HeaderProps {
  userName?: string;
}

const Header: React.FC<HeaderProps> = ({ userName = "User" }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const handleLinkClick = () => setIsMenuOpen(false);
  const navigationData = getNavigationData(userName);

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
    <header className="p-2 shadow-md bg-[rgb(246,247,249)] dark:bg-[rgb(31,39,45)]">
      <div className="sticky z-3 flex justify-between items-center">
        <Link to="/" className="text-xl font-extrabold text-[#2374bb]">
          MlflowOidcAuth
        </Link>

        <div className="flex">
          <div className="flex items-center">
            <DarkModeToggle />
            <button
              type="button"
              className="sm:hidden fill-current text-[rgb(95,114,129)] hover:text-[rgb(14,83,139)] hover:bg-[rgba(34,114,180,0.08)] dark:text-[rgb(186,225,252)] dark:hover:text-[rgb(138,202,255)] dark:hover:bg-[rgba(138,202,255,0.08)] cursor-pointer p-1 rounded transition-colors"
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
