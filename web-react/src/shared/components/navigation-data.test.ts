import { describe, it, expect } from "vitest";
import { getNavigationData } from "./navigation-data";

describe("navigation-data", () => {
    it("returns correct navigation structure", () => {
        const data = getNavigationData("testuser", "/base");
        
        expect(data.mainLinks).toHaveLength(3);
        expect(data.mainLinks[0].href).toBe("/base/");
        
        expect(data.userControls).toHaveLength(2);
        expect(data.userControls[0].label).toBe("Hello, testuser");
        expect(data.userControls[1].href).toBe("/base/logout");
    });
});
