# Excel-onboarding

1. 서비스 URL
    프론트엔드 : https://ps-onboarding-frontend-1038097021464.asia-northeast3.run.app
    백엔드 : https://ps-onboarding-backend-1038097021464.asia-northeast3.run.app

2. 과제 설명 : 
    - DB의 정보를 읽고 엑셀 파일로 만드는 기능을 수행합니다.
    - 데이터는 Google Cloud Storage에 저장됩니다.
    - 사용자는 서버에서 진행 상태를 알 수 있으며, 제공된 URL로 파일을 다운로드 가능합니다.
    - 기능이 완성될 시 디스코드 메시지로 알림을 제공합니다.

3. 아키텍처 다이어그램


4. 텍스트 흐름도


5. 포함 항목
 - Cloud Tasks 순차 처리 설정 방법 및 선택 이유
    실행 중인 태스크를 1개로 제한하였습니다. 또한 큐가 태스크를 서버로 보내는 동시에 실행 중인 태스크를 최대 1개로 제한하였습니다.
    첫 번째 태스크 요청이 완료되어 응답을 받아야 다음 태스크를 보낼 수 있으므로, 순차 처리의 방식이 되었습니다.
    --max-dispatches-per-second=1

큐가 태스크를 대상 서버로 보내는 속도를 최대 초당 1개로 제한한다. 최초 요청뿐 아니라 실패 후 재시도 요청도 이 제한에 포함된다.
 - GCS 파일 접근 방식 선택 이유
    사용자들이 쉽게 확인할 수 있도록 공개 URL을 활용하였습니다.
 - 프론트엔드 프레임워크 및 템플릿 선택 이유
    React를 사용하였습니다.
 - SSE vs 폴링 선택 이유
    폴링을 선택하였습니다. SSE의 경우 진행도를 받아오는 과정에서 서버 부하가 많아져 429 상태 코드가 나오는 것을 확인하였습니다.
 - 구현하지 못한 부분과 개선 방향
    백엔드에서 데이터를 몰아받는 상황 발생 -> 엑셀 생성 시 jobs 반환이 pending 후 excel 생성 작업이 끝나고 한번에 갱신되는 문제가 발생하였습니다. 현재 max_instance를 늘리는 방식 외에는 개선할 방법을 확인하지 못했습니다.
    








## Getting started

To make it easy for you to get started with GitLab, here's a list of recommended next steps.

Already a pro? Just edit this README.md and make it your own. Want to make it easy? [Use the template at the bottom](#editing-this-readme)!

## Add your files

- [ ] [Create](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#create-a-file) or [upload](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#upload-a-file) files
- [ ] [Add files using the command line](https://docs.gitlab.com/topics/git/add_files/#add-files-to-a-git-repository) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://git.pslab.kr/on-boarding/excel-job.git
git branch -M main
git push -uf origin main
```

## Integrate with your tools

- [ ] [Set up project integrations](http://git.pslab.kr/on-boarding/excel-job/-/settings/integrations)

## Collaborate with your team

- [ ] [Invite team members and collaborators](https://docs.gitlab.com/ee/user/project/members/)
- [ ] [Create a new merge request](https://docs.gitlab.com/ee/user/project/merge_requests/creating_merge_requests.html)
- [ ] [Automatically close issues from merge requests](https://docs.gitlab.com/ee/user/project/issues/managing_issues.html#closing-issues-automatically)
- [ ] [Enable merge request approvals](https://docs.gitlab.com/ee/user/project/merge_requests/approvals/)
- [ ] [Set auto-merge](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)

## Test and Deploy

Use the built-in continuous integration in GitLab.

- [ ] [Get started with GitLab CI/CD](https://docs.gitlab.com/ee/ci/quick_start/)
- [ ] [Analyze your code for known vulnerabilities with Static Application Security Testing (SAST)](https://docs.gitlab.com/ee/user/application_security/sast/)
- [ ] [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/ee/topics/autodevops/requirements.html)
- [ ] [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/ee/user/clusters/agent/)
- [ ] [Set up protected environments](https://docs.gitlab.com/ee/ci/environments/protected_environments.html)

***

# Editing this README

When you're ready to make this README your own, just edit this file and use the handy template below (or feel free to structure it however you want - this is just a starting point!). Thanks to [makeareadme.com](https://www.makeareadme.com/) for this template.

## Suggestions for a good README

Every project is different, so consider which of these sections apply to yours. The sections used in the template are suggestions for most open source projects. Also keep in mind that while a README can be too long and detailed, too long is better than too short. If you think your README is too long, consider utilizing another form of documentation rather than cutting out information.

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

## Badges
On some READMEs, you may see small images that convey metadata, such as whether or not all the tests are passing for the project. You can use Shields to add some to your README. Many services also have instructions for adding a badge.

## Visuals
Depending on what you are making, it can be a good idea to include screenshots or even a video (you'll frequently see GIFs rather than actual videos). Tools like ttygif can help, but check out Asciinema for a more sophisticated method.

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintainers.
