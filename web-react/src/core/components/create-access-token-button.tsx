import React, { useState, useCallback } from "react";
import { AccessTokenModal } from "./access-token-modal";

export const CreateAccessTokenButton: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const openModal = useCallback(() => setIsModalOpen(true), []);
  const closeModal = useCallback(() => setIsModalOpen(false), []);

  return (
    <>
      <button
        type="button"
        onClick={openModal}
        className="
          px-4 py-2 rounded-md font-medium transition-colors duration-200 
          bg-btn-primary dark:bg-btn-primary-dark 
          text-btn-primary-text dark:text-btn-primary-text-dark 
          hover:bg-btn-primary-hover dark:hover:bg-btn-primary-hover-dark
          shadow-md cursor-pointer
        "
      >
        Create access token
      </button>

      {isModalOpen && <AccessTokenModal onClose={closeModal} />}
    </>
  );
};
