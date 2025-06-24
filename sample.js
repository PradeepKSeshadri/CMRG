fetch('sample.json')
  .then(response => response.json())
  .then(data => {
    const container = document.getElementById('cards');
    const template = document.getElementById('template');
    data.forEach(item => {
      const clone = template.content.cloneNode(true);
      const cardHeading = clone.querySelector('.card-heading');
      const authorName = clone.querySelector('.author-name');
      const year = clone.querySelector('.year');
      const citation = clone.querySelector('.citation');
      const category = clone.querySelector('.category');
      const publicationTitle = clone.querySelector('.publication-title');
      const description = clone.querySelector('.description');
      const doi = clone.querySelector('.doi');
      const tags = clone.querySelector('.tags');
      // const tag = clone.querySelector('.tag');
      cardHeading.textContent = item.title;
      authorName.textContent = item.authors;
      year.textContent = item.year;
      citation.textContent = item.citations;
      category.textContent = item.category;
      publicationTitle.textContent = item.publicationTitle;
      description.textContent = item.description;
      doi.textContent = item.doi;
      let tagLength = item.tags.length;
      console.log(tagLength);
      for(let i = 0;i < tagLength;i++){
        const span = document.createElement("span");
        span.innerText = item.tags[i];
        tags.appendChild(span);
      }
      container.appendChild(clone);
    });
  })
  .catch(error => console.error('Error loading JSON:', error));
