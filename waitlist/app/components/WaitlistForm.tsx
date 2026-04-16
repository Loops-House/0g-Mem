'use client'

import { useState } from 'react'

type FormData = {
  name: string
  email: string
  role: string
  framework: string
  pain_point: string
  would_pay: string
}

const INITIAL: FormData = {
  name: '',
  email: '',
  role: '',
  framework: '',
  pain_point: '',
  would_pay: '',
}

const inputClass =
  'w-full bg-[#222] border border-[#444] rounded-lg px-4 py-3 text-[14px] text-white placeholder-[#888] transition-all duration-150 focus:border-[#777] focus:bg-[#262626]'

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[13px] text-[#bbb] mb-2">{label}</label>
      {children}
    </div>
  )
}

function Select({
  value,
  onChange,
  options,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  placeholder: string
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={inputClass + ' cursor-pointer pr-8 appearance-none'}
        style={{ color: value ? '#ffffff' : '#888' }}
      >
        <option value="" disabled style={{ background: '#1a1a1a', color: '#666' }}>
          {placeholder}
        </option>
        {options.map((o) => (
          <option key={o.value} value={o.value} style={{ background: '#1a1a1a', color: '#fff' }}>
            {o.label}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-[#555] text-[10px]">
        ▾
      </span>
    </div>
  )
}

function RadioGroup({
  value,
  onChange,
  options,
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <div className="flex gap-2">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={`text-[13px] px-5 py-2.5 rounded-lg border transition-all duration-150 ${
            value === o.value
              ? 'border-white bg-white text-black font-medium'
              : 'border-[#444] bg-[#222] text-[#999] hover:border-[#666] hover:text-[#ccc]'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function SuccessState({ name }: { name: string }) {
  const first = name ? name.split(' ')[0] : null
  return (
    <div className="py-6">
      <p className="text-[17px] text-white font-medium mb-2 tracking-tight">
        {first ? `You're on the list, ${first}.` : "You're on the list."}
      </p>
      <p className="text-[14px] text-[#555] leading-relaxed mb-8">
        We'll reach out when we're ready.
      </p>
      <a
        href="https://x.com/0G_Mem"
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-3 bg-white hover:bg-[#f0f0f0] text-black text-[14px] font-medium rounded-lg px-5 py-3 transition-colors duration-150"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.746l7.73-8.835L1.254 2.25H8.08l4.259 5.632L18.244 2.25zm-1.161 17.52h1.833L7.084 4.126H5.117L17.083 19.77z"/>
        </svg>
        Follow @0G_Mem for updates
      </a>
    </div>
  )
}

export default function WaitlistForm() {
  const [form, setForm] = useState<FormData>(INITIAL)
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')

  const set = (field: keyof FormData) => (value: string) =>
    setForm((f) => ({ ...f, [field]: value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setStatus('loading')
    setErrorMsg('')

    try {
      const res = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Something went wrong')
      setStatus('success')
    } catch (err) {
      setStatus('error')
      setErrorMsg(err instanceof Error ? err.message : 'Something went wrong')
      setTimeout(() => setStatus('idle'), 4000)
    }
  }

  if (status === 'success') return <SuccessState name={form.name} />

  return (
    <form onSubmit={handleSubmit} className="space-y-4">

      <div className="grid grid-cols-2 gap-3">
        <Field label="Name">
          <input
            type="text"
            placeholder="Your name"
            value={form.name}
            onChange={(e) => set('name')(e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Email">
          <input
            type="email"
            placeholder="you@example.com"
            value={form.email}
            onChange={(e) => set('email')(e.target.value)}
            required
            className={inputClass}
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Role">
          <Select
            value={form.role}
            onChange={set('role')}
            placeholder="Select"
            options={[
              { value: 'developer', label: 'Developer' },
              { value: 'founder', label: 'Founder' },
              { value: 'researcher', label: 'Researcher' },
              { value: 'enterprise', label: 'Enterprise' },
              { value: 'other', label: 'Other' },
            ]}
          />
        </Field>
        <Field label="Framework">
          <Select
            value={form.framework}
            onChange={set('framework')}
            placeholder="Select"
            options={[
              { value: 'langchain', label: 'LangChain' },
              { value: 'autogen', label: 'AutoGen' },
              { value: 'crewai', label: 'CrewAI' },
              { value: 'custom', label: 'Custom' },
              { value: 'none', label: 'None yet' },
              { value: 'other', label: 'Other' },
            ]}
          />
        </Field>
      </div>

      <Field label="Biggest frustration with AI agent memory">
        <textarea
          placeholder="What can't you do today?"
          value={form.pain_point}
          onChange={(e) => set('pain_point')(e.target.value)}
          rows={3}
          className={inputClass + ' resize-none'}
        />
      </Field>

      <Field label="Would you use a paid version?">
        <RadioGroup
          value={form.would_pay}
          onChange={set('would_pay')}
          options={[
            { value: 'yes', label: 'Yes' },
            { value: 'maybe', label: 'Maybe' },
            { value: 'no', label: 'No' },
          ]}
        />
      </Field>

      {status === 'error' && (
        <p className="text-[12px] text-red-400">{errorMsg}</p>
      )}

      <button
        type="submit"
        disabled={status === 'loading'}
        className="w-full bg-white hover:bg-[#f0f0f0] disabled:opacity-40 disabled:cursor-not-allowed text-[#0c0c0c] text-[14px] font-semibold tracking-tight rounded-lg px-4 py-2.5 transition-colors duration-150 mt-2"
      >
        {status === 'loading' ? 'Joining...' : 'Join the waitlist'}
      </button>

    </form>
  )
}
