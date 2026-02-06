library(here)
library(dplyr)

query <- function(event = "owg2022",
                  year = "2122",
                  type = "Individual",
                  category = "Men",
                  segment = "Short",
                  name = "CHEN Nathan") {
  ## ONLY MODIFY THE BODY OF THIS FUNCTION, STARTING HERE
  
  # Map argument values to local variables to avoid shadowing column names
  target_type <- type
  target_cat  <- category
  target_name <- name
  is_short    <- as.integer(segment == "Short")
  target_year <- as.integer(year)
  
  file_path <- here(event, paste0(event, ".csv"))
  df <- read.csv(file_path)
  
  target_df <- df %>%
    filter(
      tolower(event_type) == tolower(target_type),
      tolower(category)   == tolower(target_cat),
      is_short_program    == is_short,
      tolower(name)       == tolower(target_name)
    )
  
  ee_df <- target_df %>% filter(is_element == 1)
  pc_df <- target_df %>% filter(is_element == 0)
  
  judge_cols <- paste0("J", 1:9)
  
  ee_matrix <- as.matrix(ee_df[, judge_cols])
  rownames(ee_matrix) <- ee_df$element
  
  pc_matrix <- as.matrix(pc_df[, judge_cols])
  rownames(pc_matrix) <- pc_df$program_component
  
  judge_file_path <- here("judge_nationalities.csv")
  judge_df <- read.csv(judge_file_path)
  
  target_cat_num <- 
  judges_to_ret_df <- judge_df %>%
    filter(
      isu_year == target_year,
      tolower(event_type) == tolower(target_type),
      tolower(category)   == tolower(target_cat),
      is_short_program    == is_short
    ) %>%
    select(judge = judge_name, countries = judge_nationality)
  
  x <- list(
    ee = ee_matrix,
    pc = pc_matrix,
    judges = judges_to_ret_df
  )
  
  ## ONLY MODIFY THE BODY OF THIS FUNCTION, ENDING HERE
  return(x)
}
query()
