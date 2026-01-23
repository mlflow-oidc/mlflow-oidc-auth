import { describe, it, expect } from "vitest";
import * as entityService from "./entity-service";

describe("entity-service", () => {
   it("exported functions are defined", () => {
       expect(entityService.fetchAllGroups).toBeDefined();
       expect(entityService.fetchAllExperiments).toBeDefined();
       expect(entityService.fetchAllModels).toBeDefined();
       expect(entityService.fetchAllPrompts).toBeDefined();
   });

   it("all permission fetchers are defined", () => {
       expect(entityService.fetchExperimentUserPermissions).toBeDefined();
       expect(entityService.fetchUserExperimentPermissions).toBeDefined();
       expect(entityService.fetchGroupExperimentPermissions).toBeDefined();
   });
});
