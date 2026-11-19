# Python API reference

These commands and result types back the `z-spec` CLI and the `zspec` MCP
server. See the [z-spec README](https://github.com/punt-labs/z-spec#readme)
for command-line and plugin usage. Other Python modules house surface and
lux implementation details.

::: punt_zspec
    options:
      members: false

## Commands

Each command validates its inputs, runs the binary or store, and returns a
`CommandResult`. The CLI and MCP surfaces both resolve them from
`CAPABILITIES`.

::: punt_zspec.commands.registry.CAPABILITIES

::: punt_zspec.commands.registry.Capability

::: punt_zspec.commands.check.CheckCommand

::: punt_zspec.commands.test.TestCommand

::: punt_zspec.commands.animate.AnimateCommand

::: punt_zspec.commands.model_check.ModelCheckCommand

::: punt_zspec.commands.report.ReportCommand

::: punt_zspec.commands.doctor.DoctorCommand

::: punt_zspec.commands.partition.PartitionCommand

::: punt_zspec.commands.audit.AuditCommand

::: punt_zspec.commands.show.ShowCommand

::: punt_zspec.commands.browse.BrowseCommand

## Results

::: punt_zspec.commands.result.CommandResult

::: punt_zspec.commands.result.CommandError

::: punt_zspec.commands.result.CommandFailure

## Domain types

::: punt_zspec.types
    options:
      members: false

::: punt_zspec.types.fuzz.FuzzResult

::: punt_zspec.types.fuzz.FuzzError

::: punt_zspec.types.prob.ProbReport

::: punt_zspec.types.prob.CheckResult

::: punt_zspec.types.prob.CheckStatus

::: punt_zspec.types.prob.OperationCoverage

::: punt_zspec.types.trace.CounterExample

::: punt_zspec.types.trace.TraceStep

::: punt_zspec.types.partition.PartitionReport

::: punt_zspec.types.partition.OperationPartitions

::: punt_zspec.types.partition.Partition

::: punt_zspec.types.partition.PartitionStatus

::: punt_zspec.types.audit.AuditReport

::: punt_zspec.types.audit.AuditConstraint

::: punt_zspec.types.audit.AuditSuggestion

::: punt_zspec.types.audit.AuditConfidence

::: punt_zspec.types.spec.SpecModel

::: punt_zspec.types.spec.ZBlock

::: punt_zspec.types.spec.BlockKind

::: punt_zspec.types.reports.SpecReports

::: punt_zspec.types.enablement.EnablementReport

::: punt_zspec.types.enablement.EnablementAction

::: punt_zspec.types.tutorial.Collection

::: punt_zspec.types.tutorial.Lesson
