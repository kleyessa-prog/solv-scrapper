# Patient Data API

FastAPI REST API for accessing patient data from PostgreSQL database.

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Set up your database connection using environment variables (same as `save_to_db.py`):

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=solvhealth_patients
export DB_USER=postgres
export DB_PASSWORD=your_password
```

Or create a `.env` file:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=solvhealth_patients
DB_USER=postgres
DB_PASSWORD=your_password
API_HOST=0.0.0.0
API_PORT=8000
```

## Running the API

### Development Mode

```bash
python api.py
```

The API will start on `http://localhost:8000` by default.

### Production Mode

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

### With Custom Port

```bash
API_PORT=8080 python api.py
```

## API Endpoints

### GET `/`

Root endpoint with API information.

**Response:**
```json
{
  "message": "Patient Data API",
  "version": "1.0.0",
  "endpoints": {
    "GET /patient/{emr_id}": "Get patient record by EMR ID",
    "GET /docs": "API documentation (Swagger UI)",
    "GET /redoc": "Alternative API documentation (ReDoc)"
  }
}
```

### GET `/patient/{emr_id}`

Get a patient record by EMR ID.

**Parameters:**
- `emr_id` (path parameter): The EMR (Electronic Medical Record) ID of the patient

**Response (200 OK):**
```json
{
  "id": 1,
  "patient_id": "57ZXew",
  "solv_id": "solv-67",
  "emr_id": "2311340",
  "location_id": "AXjwbE",
  "location_name": "Exer Urgent Care - Demo",
  "legal_first_name": "fake 2",
  "legal_last_name": "fake",
  "first_name": "fake 2",
  "last_name": "fake",
  "mobile_phone": "(408) 234-2354",
  "dob": "11/02/1943",
  "date_of_birth": "1943-11-02",
  "reason_for_visit": "cough",
  "sex_at_birth": "",
  "gender": "",
  "room": "",
  "captured_at": "2025-11-06T14:55:33.557812",
  "created_at": "2025-11-06T15:00:00",
  "updated_at": "2025-11-06T15:00:00",
  "raw_data": {
    "location_id": "AXjwbE",
    "legalFirstName": "fake 2",
    ...
  }
}
```

**Error Responses:**

- `404 Not Found`: Patient with the given EMR ID not found
  ```json
  {
    "detail": "Patient with EMR ID '12345' not found"
  }
  ```

- `503 Service Unavailable`: Database connection error
  ```json
  {
    "detail": "Database connection error: ..."
  }
  ```

- `500 Internal Server Error`: Server error
  ```json
  {
    "detail": "Internal server error: ..."
  }
  ```

### GET `/health`

Health check endpoint to verify database connectivity.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "database": "connected"
}
```

**Response (503 Service Unavailable):**
```json
{
  "status": "unhealthy",
  "database": "disconnected",
  "error": "..."
}
```

## API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Example Usage

### Using curl

```bash
# Get patient by EMR ID
curl http://localhost:8000/patient/2311340

# Health check
curl http://localhost:8000/health
```

### Using Python requests

```python
import requests

# Get patient by EMR ID
response = requests.get("http://localhost:8000/patient/2311340")
if response.status_code == 200:
    patient = response.json()
    print(f"Patient: {patient['first_name']} {patient['last_name']}")
else:
    print(f"Error: {response.status_code} - {response.json()['detail']}")
```

### Using JavaScript fetch

```javascript
// Get patient by EMR ID
fetch('http://localhost:8000/patient/2311340')
  .then(response => response.json())
  .then(patient => {
    console.log(`Patient: ${patient.first_name} ${patient.last_name}`);
  })
  .catch(error => console.error('Error:', error));
```

## Testing

Test the API after starting it:

```bash
# Start the API
python api.py

# In another terminal, test the endpoint
curl http://localhost:8000/patient/2311340
```

## Error Handling

The API handles various error scenarios:

1. **Patient not found**: Returns 404 with a descriptive message
2. **Database connection errors**: Returns 503 Service Unavailable
3. **Invalid requests**: Returns 400 Bad Request (handled by FastAPI)
4. **Server errors**: Returns 500 Internal Server Error with error details

## CORS (Cross-Origin Resource Sharing)

If you need to access the API from a web browser, you may need to enable CORS:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Production Deployment

For production, consider:

1. **Use a production ASGI server**: Use `gunicorn` with `uvicorn` workers
   ```bash
   gunicorn api:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

2. **Set up reverse proxy**: Use Nginx or Apache in front of the API

3. **Enable HTTPS**: Use SSL/TLS certificates

4. **Add authentication**: Implement API keys or OAuth2

5. **Rate limiting**: Add rate limiting middleware

6. **Logging**: Set up proper logging and monitoring

7. **Environment variables**: Use secure secret management

## Troubleshooting

### Database Connection Error

Make sure:
- PostgreSQL is running
- Database credentials are correct
- Database exists and tables are created
- Environment variables are set correctly

### Port Already in Use

Change the port:
```bash
API_PORT=8080 python api.py
```

### Module Not Found

Install dependencies:
```bash
pip install -r requirements.txt
```

