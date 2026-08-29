@set archive_subtype=project_powerchoice
@set archive_path=..\..\Dropbox_Dan\Dropbox\pv_projects\archives\archive_%archive_subtype%_%date:~10,4%_%date:~4,2%_%date:~7,2%
@md %archive_path%
@xcopy src\*.* %archive_path% /S /exclude:exclude_backup.txt
@xcopy sample_upload_files\*.* %archive_path%\sample_upload_files\ /S
@xcopy static\*.* %archive_path%\static\ /S
@xcopy .env* %archive_path%\
@xcopy local.* %archive_path%\
@xcopy *.md* %archive_path%\

