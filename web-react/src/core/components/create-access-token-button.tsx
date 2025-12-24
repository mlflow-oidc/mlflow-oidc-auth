import React, { useState, useCallback } from "react";
import { AccessTokenModal } from "./access-token-modal";
import { Button } from "../../shared/components/button";

export const CreateAccessTokenButton: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const openModal = useCallback(() => setIsModalOpen(true), []);
  const closeModal = useCallback(() => setIsModalOpen(false), []);

  return (
    <>
      <Button
        onClick={openModal}
        variant="primary"
      >
        Create access token
      </Button>

      {isModalOpen && <AccessTokenModal onClose={closeModal} />}
    </>
  );
};
