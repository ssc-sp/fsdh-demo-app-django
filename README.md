# Astervis
Welcome to Astervis, a browser-based FITS database and visualizer.

## Setting up Astervis (Locally)
Prerequisites:
1. Visual Studios Code (Run the Dev Container)
2. WSL (Windows Subsystem for Linux) (Optional but reccomended)
3. Access to this Git repository

Steps:
1. Using Git, clone this repository to your desired location (in WSL if present)
2. Adjust the `.env` file
    - Add a `DJANGO_SECRET_KEY`
    - Add Django superuser credentials if desired
3. Open the repository as a Dev Container in VS Code
4. Wait for the container to build and run
5. Head to http://localhost/ to verify functioning of site

Adding observations:
1. Set up a Django admin/superuser account
    - This can either be done automatically using the environment variables or manually via `python manage.py createsuperuser`
2. Log in using those credentials at https://localhost/admin/
3. Click the button to add an observation location
    - The Domain should be something like `data.asc-csa.gc.ca` and the "S path" would be like `/users/OpenData_DonneesOuvertes/pub/NEOSSAT/ASTRO/2026`
    - Note: Due to changes in the header format sometime in 2024, observations taken before then may have values that are either missing or inaccessible from the search function.
4. Wait a bit (depends on how many folders/sub-folders exist)
5. Return to the main site and view all the observations

## Setting up Astervis (On the FSDH)
Prerequisites:
1. Access to the FSDH
3. Access to this Git repository

Steps:
1. In the FSDH, obtain the Web App and SQL Database tools
2. In the Web App configuration, do the following:
    - Enter the Git repo URL (https://github.com/AstralOversight/astervis.git) and Docker compose file path (`docker-compose-az.yml`)
    - Activate URL rewriting
    - Add the Environment variables found in the `.env` file to the Web App
        - Make sure to adjust them as needed
        - The `DJANGO_BASE_URL` for example will most likely resemble `/app/<Workspace Name>/`, it can be seen under `Proxy URL for development` in the Web application information section
        - The Database info can be found in the SQL Database section if you are a project lead
        - Superuser credential variables will be somewhat important as there is no direct command line access
3. Redeploy/Start/Restart the Web App as needed.

Adding observations:
1. Set up a Django admin/superuser account
    - (Via the environment variables if not already done)
2. Log in using those credentials at [Site here]/admin/
3. Click the button to add an observation location
    - The Domain should be something like `data.asc-csa.gc.ca` and the "S path" would be like `/users/OpenData_DonneesOuvertes/pub/NEOSSAT/ASTRO/2026`
    - Note: Due to changes in the header format sometime in 2024, observations taken before then may have values that are either missing or inaccessible from the search function.
4. Wait a bit (depends on how many folders/sub-folders exist)
5. Return to the main site and view all the observations