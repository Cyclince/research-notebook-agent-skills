# Provenance and acceptance bookkeeping for the R template; no scientific computation here.
# Needs jsonlite and digest, which IRkernel already depends on.

FIELDS <- strsplit(paste0("schema_version,dataset_id,source_code_version,refactor_code_version,method,check_type,",
  "sample_key,metric,old_value,new_value,abs_diff,rel_diff,atol,rtol,comparison_rule,",
  "qc_before,qc_after,status,notes"), ",")[[1]]

sha256 <- function(path) digest::digest(file = path, algo = "sha256")

# All columns as text: no NA recognition, no type guessing, no renamed headers.
read_text_table <- function(path, sep = ",", encoding = "UTF-8-BOM") {
  read.table(path, header = TRUE, sep = sep, quote = "\"", comment.char = "", colClasses = "character",
             na.strings = character(0), check.names = FALSE, fill = FALSE, strip.white = FALSE,
             fileEncoding = encoding, encoding = "UTF-8")
}

write_table <- function(table, path) {
  numeric <- vapply(table, is.numeric, logical(1))
  # 17 significant digits round-trip a double; NA is written as an empty field.
  table[numeric] <- lapply(table[numeric], function(x) ifelse(is.na(x), "", sprintf("%.17g", x)))
  text <- c(paste(quote_csv(names(table)), collapse = ","),
            if (nrow(table)) do.call(paste, c(lapply(table, quote_csv), sep = ",")))
  write_lines(text, path)
}

quote_csv <- function(x) {
  x <- as.character(x)
  special <- grepl("[\",\r\n]", x)
  x[special] <- paste0("\"", gsub("\"", "\"\"", x[special], fixed = TRUE), "\"")
  x
}

# UTF-8 with LF on every platform, replaced atomically.
write_lines <- function(text, path) {
  temporary <- paste0(path, ".tmp")
  stream <- file(temporary, "wb")
  writeBin(charToRaw(enc2utf8(paste0(paste(text, collapse = "\n"), "\n"))), stream)
  close(stream)
  if (!file.rename(temporary, path)) stop("cannot write ", path)
}

write_record <- function(record, path)
  write_lines(jsonlite::toJSON(record, auto_unbox = TRUE, pretty = TRUE, digits = NA, null = "null"), path)

read_record <- function(path) jsonlite::fromJSON(path, simplifyVector = FALSE)

# jsonlite turns the string "NA" into a missing value when simplifying, so lists stay unsimplified.
read_config <- function(path) {
  config <- read_record(path)
  for (name in c("missing_values", "key_columns"))
    if (!is.null(config[[name]])) config[[name]] <- as.character(unlist(config[[name]]))
  config
}

# Same text as the Python adapter: JSON object, keys sorted bytewise.
json_key <- function(values) {
  values <- values[sort(names(values), method = "radix")]
  quoted <- function(x) as.character(jsonlite::toJSON(as.character(x), auto_unbox = TRUE))
  paste0("{", paste(vapply(names(values), function(name) paste0(quoted(name), ": ", quoted(values[[name]])), ""), collapse = ", "), "}")
}

# Untagged code counts as calculation; only cells tagged "plot" are excluded.
science_hash <- function(path) {
  if (!file.exists(path)) stop("Notebook file ", path, " not found: set NOTEBOOK_FILE to the current file name")
  cells <- jsonlite::fromJSON(path, simplifyVector = FALSE)$cells
  keep <- Filter(function(cell) cell$cell_type == "code" && !("plot" %in% unlist(cell$metadata$tags)), cells)
  sources <- vapply(keep, function(cell) paste(unlist(cell$source), collapse = ""), "")
  digest::digest(enc2utf8(paste(trimws(sources), collapse = "\n\f\n")), algo = "sha256", serialize = FALSE)
}

# An environment, so that a status survives an error raised by a later check.
new_checks <- function(path, dataset_id, method, version, expected) {
  checks <- new.env()
  checks$path <- path
  checks$base <- list(schema_version = "1.0", dataset_id = dataset_id, source_code_version = "unknown",
                      refactor_code_version = version, method = method)
  checks$rows <- list()
  for (metric in expected) set_check(checks, metric, "NOT-RUN")
  save_checks(checks)
  checks
}

set_check <- function(checks, metric, status, notes = "", rule = "") {
  row <- as.list(setNames(rep("", length(FIELDS)), FIELDS))
  row[names(checks$base)] <- checks$base
  kind <- sub(":.*", "", metric)
  if (kind == "input") kind <- switch(metric, "input:qc" = "qc", "input:schema" = "structure", "provenance")
  row[c("check_type", "metric", "status", "notes", "comparison_rule")] <- list(kind, metric, status, notes, rule)
  checks$rows[[metric]] <- row
}

check <- function(checks, metric, condition, message) {
  ok <- isTRUE(all(condition))
  set_check(checks, metric, if (ok) "PASS" else "FAIL", if (ok) "" else message, message)
  if (!ok) {
    save_checks(checks)
    stop(message, call. = FALSE)
  }
}

save_checks <- function(checks) {
  current <- do.call(rbind, lapply(checks$rows, as.data.frame, stringsAsFactors = FALSE))
  if (file.exists(checks$path)) {
    old <- read_text_table(checks$path)
    if (!identical(names(old), FIELDS)) stop(checks$path, " does not use the validation_matrix schema")
    identity <- function(x) paste(x$dataset_id, x$method, x$check_type, x$sample_key, x$metric, sep = "\f")
    current <- rbind(old[!(identity(old) %in% identity(current)), , drop = FALSE], current)
  }
  write_table(current[FIELDS], checks$path)
}
