# Output definitions for the Firestore module
# These outputs expose essential database and App Engine attributes for use by other modules

output "database_id" {
  description = "The unique identifier of the Firestore database"
  value       = google_firestore_database.main.id
}

output "database_name" {
  description = "The name of the Firestore database"
  value       = google_firestore_database.main.name
}

output "database_location" {
  description = "The location/region where the Firestore database is deployed"
  value       = google_firestore_database.main.location_id
}

output "app_engine_id" {
  description = "The ID of the App Engine application required for Firestore"
  value       = google_app_engine_application.main.id
}