args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) stop('Usage: Rscript summarize.R readings.csv output-directory')
d <- read.csv(args[1], stringsAsFactors = FALSE)
required <- c('experiment_id', 'treatment_id', 'plot_id', 'measurement', 'value', 'timestamp')
if (!all(required %in% names(d))) stop('Input is not a FieldSense research export')
dir.create(args[2], recursive = TRUE, showWarnings = FALSE)
d$value <- as.numeric(d$value)
keys <- interaction(d$experiment_id, d$treatment_id, d$plot_id, d$measurement, drop = TRUE)
summary <- do.call(rbind, lapply(split(d, keys), function(g) {
  v <- g$value[is.finite(g$value)]
  data.frame(experiment_id=g$experiment_id[1], treatment_id=g$treatment_id[1], plot_id=g$plot_id[1], measurement=g$measurement[1], n=length(v), missing=sum(!is.finite(g$value)), mean=if(length(v)) mean(v) else NA, sd=if(length(v)>1) sd(v) else NA, median=if(length(v)) median(v) else NA)
}))
write.csv(summary, file.path(args[2], 'plot-summary.csv'), row.names=FALSE)
for (measurement in unique(d$measurement)) {
  g <- d[d$measurement == measurement & is.finite(d$value), ]
  if (!nrow(g)) next
  png(file.path(args[2], paste0(measurement, '-treatments.png')), width=1600, height=1000, res=150)
  par(mar=c(9,5,4,2))
  boxplot(value ~ treatment_id, data=g, las=2, col='#b7d3aa', main=paste('Simulated research data:', measurement), ylab=paste(measurement, g$unit[1]), xlab='')
  dev.off()
}
cat('Generated', nrow(summary), 'plot summaries. Descriptive only; repeated sensor observations are not independent replicates.\n')
