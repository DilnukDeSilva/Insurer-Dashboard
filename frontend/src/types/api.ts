export type ToolStatus = {
  name: string;
  configured: boolean;
  description: string;
};

export type HealthResponse = {
  status: string;
  service: string;
  environment?: string;
  pipeline: ToolStatus[];
};
