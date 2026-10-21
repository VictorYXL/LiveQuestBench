// Native DeepSeek harness composition, without filesystem, code, or shell tools.
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { createInterface } from 'node:readline'
import { writeFile } from 'node:fs/promises'

const lines = createInterface({ input: process.stdin })
const input = lines[Symbol.asyncIterator]()
const config = JSON.parse((await input.next()).value)
let sequence = 0
async function rpc(op, payload = {}) {
  const id = ++sequence
  process.stdout.write(JSON.stringify({ id, op, ...payload }) + '\n')
  const next = await input.next()
  if (next.done) throw new Error('Benchmark bridge closed')
  const reply = JSON.parse(next.value)
  if (reply.id !== id) throw new Error('Mismatched benchmark bridge reply')
  return reply.result
}
console.log = console.error
const root = resolve(process.argv[2])
const load = (path) => import(pathToFileURL(resolve(root, path, 'lib/index.js')).href)
const { Context } = await load('vendor/cordis')
const { default: LlmRuntime, LlmAdapter, ReasoningEffortId, ToolCallId, createUserMessage } = await load('packages/llm/llm')
const { default: SessionStore, SessionId } = await load('packages/core/session')
const { default: SessionProjection } = await load('packages/session/session-projection')
const { default: SystemPrompt } = await load('packages/core/system-prompt')
const { default: Tools } = await load('packages/core/tools')
const { default: Agents } = await load('packages/core/agent')
const { default: AgentLoop } = await load('packages/core/agent-loop')

function wireMessage(message) {
  const calls = message.content.filter(block => block.type === 'tool-call')
  const text = message.content.filter(block => block.type === 'text').map(block => block.text).join('\n')
  if (message.content.some(block => !['text', 'tool-call', 'reasoning'].includes(block.type))) {
    throw new Error('Unsupported native history block')
  }
  return {
    role: message.role, content: text || null,
    ...(calls.length ? { tool_calls: calls.map(block => ({
      id: block.id, type: 'function', function: { name: block.name, arguments: block.arguments },
    })) } : {}),
    ...(message.role === 'tool' ? { tool_call_id: message.toolCallId } : {}),
  }
}

let lastAnswer = ''
class BenchmarkModel extends LlmAdapter {
  async resolveModel(provider, model) {
    return { provider, id: model, name: model, reasoning: {
      efforts: [{ id: ReasoningEffortId(config.reasoning_effort), name: config.reasoning_effort }],
      defaultEffort: ReasoningEffortId(config.reasoning_effort),
    } }
  }
  async *stream(options) {
    if (options.signal?.aborted) throw new Error('Model request cancelled')
    const response = await rpc('chat', { request: {
      model: options.model, messages: options.messages.map(wireMessage),
      tools: options.tools.map(tool => ({ type: 'function', function: tool })),
      max_tokens: options.maxTokens, reasoning_effort: options.reasoningEffort,
      ...(options.temperature === undefined ? {} : { temperature: options.temperature }),
      ...(options.stop === undefined ? {} : { stop: options.stop }),
    } })
    if (options.signal?.aborted) throw new Error('Model request cancelled')
    const message = response.choices[0].message
    let index = 0
    if (message.content) {
      lastAnswer = message.content
      yield { type: 'block-start', index, blockType: 'text' }
      yield { type: 'text-delta', index, text: message.content }
      yield { type: 'block-end', index: index++, block: { type: 'text', text: message.content } }
    }
    for (const call of message.tool_calls ?? []) {
      const id = ToolCallId(call.id)
      yield { type: 'block-start', index, blockType: 'tool-call' }
      yield { type: 'tool-call-delta', index, id, name: call.function.name, argumentsDelta: call.function.arguments }
      yield { type: 'block-end', index: index++, block: {
        type: 'tool-call', id, name: call.function.name, arguments: call.function.arguments,
      } }
    }
    if (response.usage) {
      yield { type: 'usage', usage: {
        inputTokens: response.usage.prompt_tokens, outputTokens: response.usage.completion_tokens,
      } }
    }
    yield { type: 'finish', reason: { kind: message.tool_calls?.length ? 'tool-calls' : 'stop' } }
  }
}

const ctx = new Context()
let handle
try {
  await ctx.plugin(LlmRuntime)
  await ctx.plugin(SessionStore)
  await ctx.plugin(SessionProjection)
  await ctx.plugin(SystemPrompt, { personaPrefix: config.instructions })
  await ctx.plugin(Tools)
  await ctx.plugin(Agents)
  await ctx.plugin(AgentLoop, { agents: [], maxParallelToolCalls: 1 })
  ctx.llm.registerAdapter(['livequestbench'], new BenchmarkModel())
  for (const schema of config.tools) {
    ctx.tools.register({
      ...schema,
      output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
      async execute(args, exec) {
        if (exec.signal.aborted) throw new Error('Tool cancelled')
        return rpc('tool', { name: schema.name, arguments: args })
      },
    })
  }
  await rpc('ready', { tools: ctx.tools.schemas().map(tool => tool.name) })
  handle = await ctx.agents.create({
    sessionId: SessionId(config.episode_id),
    agentOptions: { provider: 'livequestbench', model: config.model,
      reasoningEffort: ReasoningEffortId(config.reasoning_effort), maxTokens: config.max_output_tokens },
  })
  process.on('SIGTERM', () => handle.agent.cancel({ kind: 'user' }))
  handle.agent.followup(createUserMessage({
    content: [{ type: 'text', text: config.task }], source: { kind: 'user' },
  }))
  await handle.agent.whenIdle()
  const events = handle.agent.session.snapshotEvents()
  await writeFile('native_events.json', JSON.stringify(events, null, 2) + '\n')
  const terminal = events.findLast(event => event.type === 'turn/end')
  if (terminal?.data.reason.kind !== 'completed' || !lastAnswer.trim()) {
    throw new Error(`Native turn did not complete: ${JSON.stringify(terminal?.data)}`)
  }
  await handle.dispose()
  handle = undefined
  await ctx.fiber.dispose()
  process.stdout.write(JSON.stringify({ op: 'exit', result: {
    reason: 'returned', message: lastAnswer, native_reason: 'completed',
  } }) + '\n')
} finally {
  if (handle) await handle.dispose()
  await ctx.fiber.dispose()
  lines.close()
}
