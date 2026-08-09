# Claude/Fable Update Adjudication R25

## Version lineage

Four byte-distinct reports now share nearly the same name:

| Version | Size | SHA-256 | Main delta |
|---|---:|---|---|
| V1 | 28777 | `3c7b0a24d42a86391d9f770d4d31c043409a24b60a0ffc47e517a09792246081` | initial synthesis; lost-session conclusion wrong |
| V2 | 33945 | `174d588f781770508cdd43f591fc40f5417b02b4a46dba1b3a3874c63eeb9e04` | adversarial correction and source repairs |
| V3 | 37776 | `f7543d399e8cc9f1b9d623984390a9ff4336e6b90c2cc1d12bab82f080b75f80` | 78/99 coverage audit and two named gaps |
| V4 | 38946 | `0e772ec024ddae01108fccdb5501a49369cf8ee4ec21b8de32be8cee006f6130` | two gaps read; 80/99 and new origin findings |

V4 is the latest report, but filename identity alone is insufficient.

## Accepted V4 additions

- `NFT Bot MVP Plan` is a March 16–17 origin source, not current implementation proof.
- The defensive NFT analytics product and the legacy OKX execution roadmap are separate scopes.
- `AI Tamagotchi` is the direct origin of Aigochi and imports BitEvo-derived memory/governance layers.
- The NFT archive contained an `.env`, and bridge code contained a hard-coded default database credential pattern; no value is reproduced here.
- TradingOS has incompatible metric claims inside one pack, proving the need for metric-scope binding.
- Amora is entity-ambiguous across product-shell and company/work contexts.
- Secrets management was consciously deferred under a narrow-MVP decision; the risk is not accidental, but the deferral is now expired debt unless owned and time-bounded.

## Material correction to V4

The report says the four ~5.2MB `systempack_*.md` files were Zxcvbn dictionaries. This is false. Exact bytes show project archive paths, `# SYSTEMPACK_*` headers and `# >>> segment_*` sections. The two actual Zxcvbn dictionaries are different files and hashes.

Verdict:

```text
CLAUDE_FABLE_V4 = PASS_WITH_CONDITIONS_AS_FORENSIC_REPORT
VERSION_LINEAGE_REQUIRED
SYSTEMPACK_CLASSIFICATION_REVISED
CURRENT_RUNTIME_AUTHORITY_DENIED
```
