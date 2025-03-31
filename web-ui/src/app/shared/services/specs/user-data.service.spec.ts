import { TestBed } from "@angular/core/testing";
import {
  HttpClientTestingModule,
  HttpTestingController,
} from "@angular/common/http/testing";

import { UserDataService } from "../data/user-data.service";
import { API_URL } from "src/app/core/configs/api-urls";
import {
  CurrentUserModel,
  TokenModel,
  AllUsersListModel,
} from "../../interfaces/user-data.interface";

describe("UserDataService", () => {
  let service: UserDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [UserDataService],
    });
    service = TestBed.inject(UserDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it("should be created", () => {
    expect(service).toBeTruthy();
  });

  it("should return the current user", () => {
    const mockUser: CurrentUserModel = {
      id: 1,
      display_name: "John Doe",
      username: "john.doe@example.com",
      experiments: [],
      is_admin: false,
      models: [],
      prompts: [],
    };

    const mockResponse = {
      user: mockUser,
      models: [],
      experiments: [],
      prompts: [],
    };

    service.getCurrentUser().subscribe((response) => {
      expect(response).toEqual(mockResponse);
    });

    const req = httpMock.expectOne(API_URL.GET_CURRENT_USER);
    expect(req.request.method).toBe("GET");
    req.flush(mockUser);

    const modelsReq = httpMock.expectOne(
      API_URL.MODELS_FOR_USER.replace("${userName}", mockUser.username),
    );
    expect(modelsReq.request.method).toBe("GET");
    modelsReq.flush({ models: [] });

    const experimentsReq = httpMock.expectOne(
      API_URL.EXPERIMENTS_FOR_USER.replace("${userName}", mockUser.username),
    );
    expect(experimentsReq.request.method).toBe("GET");
    experimentsReq.flush({ experiments: [] });

    const promptsReq = httpMock.expectOne(
      API_URL.PROMPTS_FOR_USER.replace("${userName}", mockUser.username),
    );
    expect(promptsReq.request.method).toBe("GET");
    promptsReq.flush({ prompts: [] });
  });

  it("should return the access key", () => {
    const mockAccessKey: TokenModel = { token: "mock-access-key" };

    service.getAccessKey().subscribe((token) => {
      expect(token).toEqual(mockAccessKey);
    });

    const req = httpMock.expectOne(API_URL.GET_ACCESS_TOKEN);
    expect(req.request.method).toBe("GET");
    req.flush(mockAccessKey);
  });

  it("should return all users", () => {
    const mockUsers: AllUsersListModel = {
      users: ["John Doe", "Jane Smith"],
    };

    service.getAllUsers().subscribe((users) => {
      expect(users).toEqual(mockUsers);
    });

    const req = httpMock.expectOne(API_URL.GET_ALL_USERS);
    expect(req.request.method).toBe("GET");
    req.flush(mockUsers);
  });
});
