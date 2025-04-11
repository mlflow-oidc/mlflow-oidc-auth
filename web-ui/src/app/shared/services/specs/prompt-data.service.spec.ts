import { TestBed } from "@angular/core/testing";
import {
  HttpClientTestingModule,
  HttpTestingController,
} from "@angular/common/http/testing";
import { PromptsDataService } from "../data/prompt-data.service";
import { API_URL } from "src/app/core/configs/api-urls";
import {
  PromptModel,
  PromptPermissionsModel,
  PromptUserListModel,
} from "src/app/shared/interfaces/prompts-data.interface";
import {
  PermissionEnum,
  PermissionTypeEnum,
} from "src/app/core/configs/permissions";
describe("PromptsDataService", () => {
  let service: PromptsDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [PromptsDataService],
    });
    service = TestBed.inject(PromptsDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it("should be created", () => {
    expect(service).toBeTruthy();
  });

  it("should fetch all prompts", () => {
    const mockPrompts: PromptModel[] = [
      { name: "Prompt 1", description: "", tags: {}, aliases: {} },
      { name: "Prompt 2", description: "", tags: {}, aliases: {} },
    ];
    service.getAllPrompts().subscribe((prompts) => {
      expect(prompts).toEqual(mockPrompts);
    });

    const req = httpMock.expectOne(API_URL.ALL_PROMPTS);
    expect(req.request.method).toBe("GET");
    req.flush(mockPrompts);
  });

  it("should fetch prompts for a user", () => {
    const userName = "testUser";
    const mockResponse: PromptPermissionsModel = {
      prompts: [
        {
          name: "prompt 1",
          permission: PermissionEnum.MANAGE,
          type: PermissionTypeEnum.USER,
        },
        {
          name: "prompt 2",
          permission: PermissionEnum.READ,
          type: PermissionTypeEnum.FALLBACK,
        },
      ],
    };
    const expectedPrompts = mockResponse.prompts;

    service.getPromptsForUser(userName).subscribe((prompts) => {
      expect(prompts).toEqual(expectedPrompts);
    });

    const req = httpMock.expectOne(
      API_URL.PROMPTS_FOR_USER.replace("${userName}", userName),
    );
    expect(req.request.method).toBe("GET");
    req.flush(mockResponse);
  });

  it("should fetch users for a prompt", () => {
    const promptName = "testPrompt";
    const mockUsers: PromptUserListModel[] = [
      { permission: PermissionEnum.EDIT, username: "User 1" },
      { permission: PermissionEnum.MANAGE, username: "User 2" },
    ];

    service.getUsersForPrompt(promptName).subscribe((users) => {
      expect(users).toEqual(mockUsers);
    });

    const req = httpMock.expectOne(
      API_URL.USERS_FOR_PROMPT.replace("${promptName}", promptName),
    );
    expect(req.request.method).toBe("GET");
    req.flush(mockUsers);
  });
});
