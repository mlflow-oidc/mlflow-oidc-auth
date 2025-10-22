import React from "react";

interface NavLinkProps extends React.PropsWithChildren {
  href: string;
  onClick?: () => void;
}

const NavLink: React.FC<NavLinkProps> = ({ href, children, onClick }) => {
  const baseClasses =
    "p-2 w-full sm:w-auto text-[rgb(95,114,129)] hover:text-[rgb(14,83,139)] dark:text-[rgb(146,164,179)] dark:hover:text-[rgb(138,202,255)] text-lg sm:text-sm font-medium transition-colors text-left sm:text-center rounded-md";
  return (
    <a href={href} className={baseClasses} onClick={onClick}>
      {children}
    </a>
  );
};

export default NavLink;
