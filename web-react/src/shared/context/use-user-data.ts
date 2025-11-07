import { use } from "react";
import { UserContext } from "../context/user-provider";

export const useUserData = () => use(UserContext);
