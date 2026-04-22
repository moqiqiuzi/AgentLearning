# CODING.md

## 编码规范 v1.0

本规范适用于 AI 知识库项目（Python + TypeScript 双技术栈），确保代码质量、可维护性和团队协作效率。

---

## 1. Python 编码规范

### 1.1 基础规范

遵循 **PEP 8** 标准，使用以下工具强制执行：
- `black`: 代码格式化（行长度 88 字符）
- `isort`: import 排序
- `flake8`: 代码检查
- `mypy`: 类型检查（严格模式）
- `pylint`: 代码质量

### 1.2 命名规范

```python
# 文件名: snake_case.py
# 包名: snake_case
# 模块名: snake_case

# 类名: PascalCase
class GitHubCollector:
    pass

# 函数/方法名: snake_case
def fetch_trending_data():
    pass

# 常量: UPPER_CASE
MAX_RETRIES = 3
API_TIMEOUT = 30

# 私有方法: _prefix
def _validate_response(self):
    pass

# 受保护方法: __prefix
def __init__(self):
    pass
```

### 1.3 类型注解

所有函数必须包含类型注解，使用 Python 3.11+ 特性：

```python
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

@dataclass
class Project:
    name: str
    url: str
    stars: int
    forks: int
    updated_at: str

async def fetch_projects(
    limit: int = 30,
    keywords: List[str] | None = None,
) -> List[Project]:
    if keywords is None:
        keywords = []
    
    # 实现逻辑
    return []
```

### 1.4 Agent 开发规范

#### 1.4.1 Agent 基类结构

```python
from abc import ABC, abstractmethod
from typing import Any, Dict
from dataclasses import dataclass

@dataclass
class AgentResult:
    success: bool
    data: Dict[str, Any] | None = None
    error: str | None = None
    metadata: Dict[str, Any] | None = None

class BaseAgent(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self) -> None:
        pass
    
    @abstractmethod
    async def run(self, input_data: Any) -> AgentResult:
        pass
    
    async def execute(self, input_data: Any) -> AgentResult:
        try:
            return await self.run(input_data)
        except Exception as e:
            return AgentResult(
                success=False,
                error=str(e),
                metadata={"agent": self.__class__.__name__}
            )
```

#### 1.4.2 Collector Agent 示例

```python
import requests
from bs4 import BeautifulSoup
from typing import List

class CollectorAgent(BaseAgent):
    AI_KEYWORDS = [
        "AI", "ML", "Machine Learning", "Deep Learning",
        "LLM", "NLP", "Computer Vision", "GPT", "Claude",
        "Transformer", "PyTorch", "TensorFlow"
    ]
    
    async def run(self, input_data: Any) -> AgentResult:
        projects = await self._fetch_trending()
        filtered = self._filter_ai_projects(projects)
        
        return AgentResult(
            success=True,
            data={"projects": filtered},
            metadata={"total": len(filtered)}
        )
    
    async def _fetch_trending(self) -> List[Dict[str, Any]]:
        # 实现抓取逻辑
        pass
    
    def _filter_ai_projects(self, projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # 实现过滤逻辑
        pass
```

#### 1.4.3 Analyzer Agent 示例

```python
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

class AnalyzerAgent(BaseAgent):
    SCORING_DIMENSIONS = [
        "tech_value", "practicality", "usability",
        "activity", "overall"
    ]
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.llm = ChatOpenAI(
            model=config.get("model", "gpt-4"),
            temperature=0.3
        )
        self.prompt = self._build_prompt()
    
    async def run(self, input_data: Any) -> AgentResult:
        project = input_data
        
        try:
            analysis = await self._analyze_project(project)
            return AgentResult(
                success=True,
                data=analysis
            )
        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Analysis failed: {e}"
            )
    
    async def _analyze_project(self, project: Dict[str, Any]) -> Dict[str, Any]:
        # 实现分析逻辑
        pass
```

### 1.5 异步编程规范

```python
import asyncio
from typing import List, Any

async def process_projects(projects: List[Any]) -> List[Any]:
    tasks = [self._analyze_project(p) for p in projects]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    valid_results = [r for r in results if isinstance(r, dict)]
    return valid_results

async def batch_process(items: List[Any], batch_size: int = 10) -> List[Any]:
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_results = await process_projects(batch)
        results.extend(batch_results)
    return results
```

### 1.6 错误处理

```python
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class AgentError(Exception):
    pass

class CollectorError(AgentError):
    pass

def safe_execute(operation: str, retries: int = 3) -> Optional[Any]:
    for attempt in range(retries):
        try:
            return _do_operation()
        except requests.RequestException as e:
            logger.warning(f"{operation} failed, attempt {attempt + 1}/{retries}: {e}")
            if attempt == retries - 1:
                raise CollectorError(f"Failed after {retries} attempts") from e
            await asyncio.sleep(2 ** attempt)
    return None
```

### 1.7 配置管理

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class AgentConfig(BaseSettings):
    api_key: str = Field(..., env="OPENAI_API_KEY")
    model: str = Field(default="gpt-4")
    temperature: float = Field(default=0.3, ge=0, le=2)
    max_retries: int = Field(default=3, ge=1, le=10)
    timeout: int = Field(default=30, ge=1)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

config = AgentConfig()
```

---

## 2. TypeScript 编码规范

### 2.1 基础规范

使用 **ESLint** + **Prettier**：
```json
{
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:prettier/recommended"
  ],
  "rules": {
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/explicit-function-return-type": "warn",
    "@typescript-eslint/no-unused-vars": "error"
  }
}
```

### 2.2 命名规范

```typescript
// 文件名: kebab-case.ts
// 接口/类型: PascalCase
interface Project {
  name: string;
  url: string;
  stars: number;
}

// 类: PascalCase
class GitHubCollector {
  // 属性: camelCase
  private readonly apiKey: string;
  
  // 方法: camelCase
  public async fetchProjects(): Promise<Project[]> {
    // 实现
    return [];
  }
  
  // 私有方法: _prefix
  private _validateResponse(response: Response): boolean {
    return response.ok;
  }
}

// 常量: UPPER_SNAKE_CASE
const MAX_RETRIES = 3;
const API_TIMEOUT = 30;

// 枚举: PascalCase
enum Priority {
  High = "high",
  Medium = "medium",
  Low = "low",
}

// 类型别名: PascalCase
type AgentResult<T> = {
  success: boolean;
  data?: T;
  error?: string;
};
```

### 2.3 类型定义

```typescript
// 使用接口定义数据结构
interface AnalysisResult {
  techValue: number;
  practicality: number;
  usability: number;
  activity: number;
  overall: number;
  reason: string;
  priority: Priority;
  tags: string[];
  techStack: string[];
  useCases: string[];
}

// 使用类型别名定义联合类型
type AgentStatus = "idle" | "running" | "completed" | "failed";

// 使用泛型提高复用性
interface AgentResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  metadata?: Record<string, unknown>;
}

// 使用 Utility Types
type PartialProject = Partial<Project>;
type ReadonlyProject = Readonly<Project>;
type ProjectKeys = keyof Project;
```

### 2.4 Agent 开发规范

```typescript
// Base Agent 类
abstract class BaseAgent<TInput, TOutput> {
  protected readonly config: Record<string, unknown>;
  
  constructor(config: Record<string, unknown>) {
    this.config = config;
    this.validateConfig();
  }
  
  protected abstract validateConfig(): void;
  
  protected abstract run(input: TInput): Promise<AgentResponse<TOutput>>;
  
  public async execute(input: TInput): Promise<AgentResponse<TOutput>> {
    try {
      return await this.run(input);
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : String(error),
        metadata: { agent: this.constructor.name },
      };
    }
  }
}

// Collector Agent 示例
interface CollectorInput {
  limit?: number;
  keywords?: string[];
}

interface CollectorOutput {
  projects: Project[];
  collectedAt: string;
  totalCount: number;
}

class CollectorAgent extends BaseAgent<CollectorInput, CollectorOutput> {
  private readonly AI_KEYWORDS = [
    "AI", "ML", "Machine Learning", "Deep Learning",
    "LLM", "NLP", "Computer Vision", "GPT", "Claude",
    "Transformer", "PyTorch", "TensorFlow",
  ] as const;
  
  protected validateConfig(): void {
    if (!this.config.apiKey) {
      throw new Error("API key is required");
    }
  }
  
  protected async run(input: CollectorInput): Promise<AgentResponse<CollectorOutput>> {
    const projects = await this.fetchTrending(input);
    const filtered = this.filterAIProjects(projects);
    
    return {
      success: true,
      data: {
        projects: filtered,
        collectedAt: new Date().toISOString(),
        totalCount: filtered.length,
      },
    };
  }
  
  private async fetchTrending(input: CollectorInput): Promise<Project[]> {
    // 实现抓取逻辑
    return [];
  }
  
  private filterAIProjects(projects: Project[]): Project[] {
    // 实现过滤逻辑
    return projects;
  }
}
```

### 2.5 异步编程

```typescript
async function processProjects(projects: Project[]): Promise<AnalysisResult[]> {
  const tasks = projects.map(p => this.analyzeProject(p));
  const results = await Promise.allSettled(tasks);
  
  const validResults = results
    .filter((r): r is PromiseFulfilledResult<AnalysisResult> => 
      r.status === "fulfilled"
    )
    .map(r => r.value);
  
  return validResults;
}

async function batchProcess<T>(
  items: T[],
  processor: (item: T) => Promise<void>,
  batchSize: number = 10
): Promise<void> {
  for (let i = 0; i < items.length; i += batchSize) {
    const batch = items.slice(i, i + batchSize);
    await Promise.all(batch.map(processor));
  }
}
```

### 2.6 错误处理

```typescript
class AgentError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly context?: Record<string, unknown>
  ) {
    super(message);
    this.name = "AgentError";
  }
}

class CollectorError extends AgentError {
  constructor(message: string, context?: Record<string, unknown>) {
    super(message, "COLLECTOR_ERROR", context);
    this.name = "CollectorError";
  }
}

async function safeExecute<T>(
  operation: string,
  fn: () => Promise<T>,
  retries: number = 3
): Promise<T> {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      if (attempt === retries - 1) {
        throw new CollectorError(
          `Failed after ${retries} attempts`,
          { operation }
        );
      }
      await new Promise(resolve => 
        setTimeout(resolve, Math.pow(2, attempt) * 1000)
      );
    }
  }
  throw new Error("Unreachable");
}
```

### 2.7 配置管理

```typescript
interface AgentConfig {
  apiKey: string;
  model: string;
  temperature: number;
  maxRetries: number;
  timeout: number;
}

class ConfigManager {
  private static instance: ConfigManager;
  private config: AgentConfig;
  
  private constructor() {
    this.config = {
      apiKey: process.env.OPENAI_API_KEY ?? "",
      model: process.env.MODEL ?? "gpt-4",
      temperature: parseFloat(process.env.TEMPERATURE ?? "0.3"),
      maxRetries: parseInt(process.env.MAX_RETRIES ?? "3", 10),
      timeout: parseInt(process.env.TIMEOUT ?? "30", 10),
    };
    this.validateConfig();
  }
  
  public static getInstance(): ConfigManager {
    if (!ConfigManager.instance) {
      ConfigManager.instance = new ConfigManager();
    }
    return ConfigManager.instance;
  }
  
  public getConfig(): Readonly<AgentConfig> {
    return this.config;
  }
  
  private validateConfig(): void {
    if (!this.config.apiKey) {
      throw new Error("OPENAI_API_KEY is required");
    }
  }
}

export const config = ConfigManager.getInstance().getConfig();
```

---

## 3. 测试规范

### 3.1 Python 测试

使用 `pytest` + `pytest-asyncio`：

```python
import pytest
from unittest.mock import AsyncMock, patch
from collector import CollectorAgent

@pytest.fixture
def collector_config():
    return {
        "api_key": "test_key",
        "timeout": 30
    }

@pytest.fixture
def collector(collector_config):
    return CollectorAgent(collector_config)

@pytest.mark.asyncio
async def test_fetch_projects_success(collector):
    mock_response = {
        "projects": [
            {"name": "test-project", "stars": 100}
        ]
    }
    
    with patch.object(collector, '_fetch_trending', return_value=mock_response["projects"]):
        result = await collector.execute(None)
        
    assert result.success
    assert len(result.data["projects"]) == 1

@pytest.mark.asyncio
async def test_fetch_projects_failure(collector):
    with patch.object(collector, '_fetch_trending', side_effect=Exception("API Error")):
        result = await collector.execute(None)
        
    assert not result.success
    assert "API Error" in result.error
```

### 3.2 TypeScript 测试

使用 `jest` + `@testing-library/react`（如有前端）：

```typescript
import { CollectorAgent } from "./Collector";

describe("CollectorAgent", () => {
  let collector: CollectorAgent;
  
  const mockConfig = {
    apiKey: "test_key",
    timeout: 30,
  };
  
  beforeEach(() => {
    collector = new CollectorAgent(mockConfig);
  });
  
  describe("execute", () => {
    it("should return success with projects", async () => {
      const mockProjects = [
        { name: "test-project", stars: 100 },
      ];
      
      jest.spyOn(collector as any, "fetchTrending")
        .mockResolvedValue(mockProjects);
      
      const result = await collector.execute({});
      
      expect(result.success).toBe(true);
      expect(result.data?.projects).toHaveLength(1);
    });
    
    it("should return failure on error", async () => {
      jest.spyOn(collector as any, "fetchTrending")
        .mockRejectedValue(new Error("API Error"));
      
      const result = await collector.execute({});
      
      expect(result.success).toBe(false);
      expect(result.error).toContain("API Error");
    });
  });
});
```

### 3.3 覆盖率要求

- 单元测试覆盖率 ≥ 80%
- 核心业务逻辑覆盖率 ≥ 90%
- 所有公共 API 必须有测试

---

## 4. 项目结构规范

```
ai-knowledge-base/
├── agents/                      # Agent 实现
│   ├── __init__.py
│   ├── base.py                 # Agent 基类
│   ├── collector/
│   │   ├── __init__.py
│   │   ├── agent.py            # Collector Agent
│   │   └── schemas.py          # 数据模型
│   ├── analyzer/
│   │   ├── __init__.py
│   │   ├── agent.py            # Analyzer Agent
│   │   └── prompts.py          # 提示词模板
│   ├── organizer/
│   │   ├── __init__.py
│   │   └── agent.py
│   └── publisher/
│       ├── __init__.py
│       ├── agent.py
│       └── templates/          # 邮件模板
│           └── daily_report.md
├── utils/                       # 工具函数
│   ├── __init__.py
│   ├── logger.py
│   ├── cache.py
│   └── validators.py
├── config/                      # 配置文件
│   ├── __init__.py
│   ├── settings.py
│   └── prompts/
├── tests/                       # 测试
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_collector.py
│   │   └── test_analyzer.py
│   └── integration/
├── data/                        # 数据目录
│   ├── knowledge_items/
│   │   └── 2024-04-21.json
│   └── cache/
├── scripts/                     # 脚本
│   ├── run_daily.sh
│   └── setup.py
├── frontend/                    # TypeScript 前端（如有）
│   ├── src/
│   │   ├── agents/
│   │   ├── components/
│   │   └── utils/
│   ├── tests/
│   └── package.json
├── pyproject.toml               # Python 依赖
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── AGENTS.md
└── CODING.md
```

---

## 5. Git 提交规范

### 5.1 提交信息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 5.2 Type 类型

- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具链相关

### 5.3 Scope 范围

- `collector`: Collector Agent
- `analyzer`: Analyzer Agent
- `organizer`: Organizer Agent
- `publisher`: Publisher Agent
- `base`: 基础设施
- `utils`: 工具函数
- `config`: 配置

### 5.4 示例

```
feat(collector): add GitHub Trending filtering by keywords

- Implement keyword-based filtering for AI projects
- Add fallback strategy when < 30 projects found
- Update schema to include filtered metadata

Closes #123
```

```
fix(analyzer): handle API rate limiting gracefully

- Add retry logic with exponential backoff
- Implement rate limit detection
- Add logging for retry attempts

Related to #156
```

---

## 6. 文档规范

### 6.1 文档字符串

Python 使用 Google Style：

```python
def fetch_projects(limit: int = 30) -> List[Project]:
    """Fetch trending projects from GitHub.
    
    Args:
        limit: Maximum number of projects to fetch. Defaults to 30.
    
    Returns:
        List of trending projects with metadata.
    
    Raises:
        CollectorError: If fetching fails after max retries.
    
    Example:
        >>> projects = fetch_projects(limit=50)
        >>> len(projects)
        50
    """
    pass
```

TypeScript 使用 JSDoc：

```typescript
/**
 * Fetches trending projects from GitHub.
 * 
 * @param limit - Maximum number of projects to fetch. Defaults to 30.
 * @returns List of trending projects with metadata.
 * @throws {CollectorError} If fetching fails after max retries.
 * 
 * @example
 * ```ts
 * const projects = await fetchProjects({ limit: 50 });
 * console.log(projects.length); // 50
 * ```
 */
async function fetchProjects(options: { limit?: number }): Promise<Project[]> {
  // 实现
  return [];
}
```

### 6.2 代码注释

```python
# TODO: 实现去重逻辑（基于 URL）
# FIXME: 时区处理需要改进
# NOTE: 这个 API 有速率限制，注意并发控制
# HACK: 临时解决方案，后续需要重构

def process_project(project: Dict[str, Any]) -> AnalysisResult:
    """
    处理单个项目，返回分析结果。
    
    流程：
    1. 验证数据完整性
    2. 调用 LLM 进行分析
    3. 解析并验证结果
    4. 返回结构化数据
    """
    pass
```

```typescript
// TODO: Implement deduplication logic (based on URL)
// FIXME: Timezone handling needs improvement
// NOTE: This API has rate limits, be careful with concurrency
// HACK: Temporary workaround, needs refactoring later

/**
 * Processes a single project and returns analysis results.
 * 
 * Workflow:
 * 1. Validate data completeness
 * 2. Call LLM for analysis
 * 3. Parse and validate results
 * 4. Return structured data
 */
function processProject(project: Project): AnalysisResult {
  // 实现
  return {} as AnalysisResult;
}
```

---

## 7. 性能和安全规范

### 7.1 性能

- 使用连接池（HTTP/数据库）
- 实现缓存策略（Redis）
- 批量处理避免循环调用
- 使用异步 I/O
- 限制并发请求数

### 7.2 安全

- 敏感信息使用环境变量
- API Key 不提交到代码库
- 输入验证和清理
- 速率限制和重试策略
- 使用 HTTPS

---

## 8. 工具配置

### 8.1 Python 配置

**pyproject.toml**:
```toml
[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=agents --cov-report=html"
```

### 8.2 TypeScript 配置

**tsconfig.json**:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "lib": ["ES2022"],
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "moduleResolution": "node",
    "types": ["node", "jest"]
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

**package.json**:
```json
{
  "scripts": {
    "lint": "eslint src --ext .ts",
    "format": "prettier --write \"src/**/*.ts\"",
    "test": "jest",
    "typecheck": "tsc --noEmit",
    "build": "tsc"
  }
}
```

---

## 9. 版本信息

- **文档版本**: v1.0
- **适用项目**: AI 知识库
- **创建日期**: 2024-04-21
- **维护者**: 技术团队
