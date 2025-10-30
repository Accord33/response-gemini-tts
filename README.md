# My FastAPI Application

This project is a FastAPI application that generates audio data and returns it as a WAV file through an API endpoint.

## Project Structure

```
my-fastapi-app
├── app
│   ├── app5.py               # Entry point for the FastAPI application, defines API endpoints for audio generation.
│   ├── __init__.py           # Empty file to treat the app directory as a package.
│   └── requirements.txt       # Lists project dependencies including FastAPI and other necessary libraries.
├── docker-compose.yml         # Docker Compose configuration file for defining services and network settings.
├── Dockerfile                 # Configuration file for building the Docker image of the application.
├── .env                       # File for defining environment variables, such as API keys and other sensitive information.
├── .dockerignore              # Specifies files and directories to ignore during Docker build.
└── README.md                  # Documentation for the project, including description and usage instructions.
```

## Getting Started

To run the application, you can use Docker Compose. Make sure you have Docker and Docker Compose installed on your machine.

### Build and Run

1. Clone the repository:
   ```
   git clone <repository-url>
   cd my-fastapi-app
   ```

2. Build and run the application using Docker Compose:
   ```
   docker-compose up --build
   ```

3. Access the API at `http://localhost:8000`.

### API Endpoints

- **POST /audio**: Generates audio based on the provided prompt and returns a WAV file.

### Dependencies

The project dependencies are listed in `app/requirements.txt`. Make sure to install them if you are running the application locally without Docker.

### Environment Variables

Make sure to set the necessary environment variables in the `.env` file, especially the `GEMINI_API_KEY` for the audio generation service.

### License

This project is licensed under the MIT License. See the LICENSE file for more details.